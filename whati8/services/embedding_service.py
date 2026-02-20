"""
Embedding service with Cohere primary and Ollama fallback.

Provides semantic embeddings for food search. Uses Cohere embed-english-v3.0
as the primary provider (best retrieval quality) and falls back to Ollama's
nomic-embed-text when Cohere is unavailable or quota-exceeded.

Both models output 768-dimensional vectors. Cohere uses Matryoshka truncation
from its native 1024 dims; nomic-embed-text is natively 768.

IMPORTANT: Vectors from different models are NOT interchangeable. Each model
gets its own column in the database, and queries use the column matching the
model that produced the query embedding.
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import httpx

from whati8.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768

# Cohere config
COHERE_API_URL = "https://api.cohere.com/v2/embed"
COHERE_MODEL = "embed-english-v3.0"
COHERE_BATCH_SIZE = 96  # Cohere allows up to 96 texts per request

# Ollama config
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "nomic-embed-text"
OLLAMA_BATCH_SIZE = 50  # Conservative batch size for local inference


class EmbeddingProvider(str, Enum):
    COHERE = "cohere"
    OLLAMA = "ollama"


@dataclass
class EmbeddingResult:
    """Result from an embedding call."""
    vectors: list[list[float]]
    provider: EmbeddingProvider
    model: str


async def _embed_cohere(
    texts: list[str],
    input_type: str = "search_document",
    timeout: float = 30.0,
) -> EmbeddingResult:
    """
    Embed texts using Cohere embed-english-v3.0.

    Args:
        texts: List of strings to embed.
        input_type: "search_document" for corpus, "search_query" for queries.
        timeout: HTTP timeout in seconds.

    Returns:
        EmbeddingResult with 768-dim vectors.

    Raises:
        Exception on API errors, quota issues, or timeouts.
    """
    api_key = getattr(settings, "cohere_api_key", "") or ""
    if not api_key:
        raise ValueError("COHERE_API_KEY not configured")

    all_vectors: list[list[float]] = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        for i in range(0, len(texts), COHERE_BATCH_SIZE):
            batch = texts[i : i + COHERE_BATCH_SIZE]
            resp = await client.post(
                COHERE_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "texts": batch,
                    "model": COHERE_MODEL,
                    "input_type": input_type,
                    "embedding_types": ["float"],
                    "truncate": "END",
                    # Request 768 dims via Matryoshka
                    # Note: Cohere v2 API doesn't have a 'dimensions' param yet
                    # for embed-english-v3.0. If it returns 1024, we truncate.
                },
            )

            if resp.status_code == 429:
                raise Exception("Cohere rate limit / quota exceeded")
            resp.raise_for_status()

            data = resp.json()
            embeddings = data.get("embeddings", {})

            # v2 API returns {"float": [[...], ...]}
            if isinstance(embeddings, dict):
                vecs = embeddings.get("float", [])
            else:
                vecs = embeddings

            # Truncate to 768 if Cohere returns 1024 (Matryoshka property)
            for vec in vecs:
                all_vectors.append(vec[:EMBEDDING_DIM])

            # Rate limiting between batches
            if i + COHERE_BATCH_SIZE < len(texts):
                await asyncio.sleep(0.5)

    return EmbeddingResult(
        vectors=all_vectors,
        provider=EmbeddingProvider.COHERE,
        model=COHERE_MODEL,
    )


async def _embed_ollama(
    texts: list[str],
    timeout: float = 60.0,
) -> EmbeddingResult:
    """
    Embed texts using Ollama nomic-embed-text.

    Args:
        texts: List of strings to embed.
        timeout: HTTP timeout in seconds.

    Returns:
        EmbeddingResult with 768-dim vectors.

    Raises:
        Exception on connection errors or model not available.
    """
    all_vectors: list[list[float]] = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        for i in range(0, len(texts), OLLAMA_BATCH_SIZE):
            batch = texts[i : i + OLLAMA_BATCH_SIZE]

            # Ollama supports batch embedding via the /api/embed endpoint
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/embed",
                json={
                    "model": OLLAMA_MODEL,
                    "input": batch,
                },
            )
            resp.raise_for_status()

            data = resp.json()
            vecs = data.get("embeddings", [])
            all_vectors.extend(vecs)

            if i + OLLAMA_BATCH_SIZE < len(texts):
                await asyncio.sleep(0.1)

    return EmbeddingResult(
        vectors=all_vectors,
        provider=EmbeddingProvider.OLLAMA,
        model=OLLAMA_MODEL,
    )


async def embed_texts(
    texts: list[str],
    input_type: str = "search_document",
    provider: Optional[EmbeddingProvider] = None,
) -> EmbeddingResult:
    """
    Embed texts using Cohere (primary) with Ollama fallback.

    Args:
        texts: List of strings to embed.
        input_type: "search_document" for corpus, "search_query" for queries.
            Only used by Cohere; Ollama ignores this.
        provider: Force a specific provider (skip fallback logic).

    Returns:
        EmbeddingResult with provider info and vectors.

    Raises:
        Exception if both providers fail.
    """
    if not texts:
        return EmbeddingResult(vectors=[], provider=EmbeddingProvider.COHERE, model="")

    if provider == EmbeddingProvider.OLLAMA:
        return await _embed_ollama(texts)
    if provider == EmbeddingProvider.COHERE:
        return await _embed_cohere(texts, input_type=input_type)

    # Default: try Cohere first, fall back to Ollama
    cohere_err = None
    try:
        result = await _embed_cohere(texts, input_type=input_type)
        logger.debug(f"Embedded {len(texts)} texts via Cohere")
        return result
    except Exception as e:
        cohere_err = e
        logger.warning(f"Cohere embedding failed ({e}), falling back to Ollama")

    try:
        result = await _embed_ollama(texts)
        logger.info(f"Embedded {len(texts)} texts via Ollama (fallback)")
        return result
    except Exception as e2:
        raise Exception(
            f"All embedding providers failed. Cohere: {cohere_err}, Ollama: {e2}"
        ) from e2


async def embed_query(query: str) -> tuple[list[float], EmbeddingProvider]:
    """
    Embed a single search query. Convenience wrapper.

    Returns:
        Tuple of (embedding vector, provider used).
    """
    result = await embed_texts([query], input_type="search_query")
    return result.vectors[0], result.provider


async def embed_corpus(
    texts: list[str],
    provider: EmbeddingProvider,
) -> list[list[float]]:
    """
    Embed corpus texts with a specific provider (for pre-computing).

    Args:
        texts: Food names to embed.
        provider: Which provider to use.

    Returns:
        List of embedding vectors (same order as input).
    """
    result = await embed_texts(
        texts,
        input_type="search_document",
        provider=provider,
    )
    return result.vectors
