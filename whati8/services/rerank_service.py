"""
Cohere Rerank service for search result optimization.

Reranks search results using Cohere's Rerank 3 model for improved relevance.
Supports multiple reranking strategies (word-count based, confidence-based, always).
"""

import logging
from enum import Enum
from typing import Optional

import httpx

from whati8.config import settings, app_config

logger = logging.getLogger(__name__)

RERANK_API_URL = "https://api.cohere.com/v2/rerank"
RERANK_MODEL = "rerank-3"


class RerankStrategy(str, Enum):
    """Strategy for when to apply reranking."""
    
    NEVER = "never"  # Disable reranking
    ALWAYS = "always"  # Always rerank
    WORD_COUNT = "word_count"  # Rerank if query has >= N words (default 3)
    CONFIDENCE = "confidence"  # Rerank if top score < threshold (default 0.6)


class RerankConfig:
    """Configuration for reranking behavior."""
    
    def __init__(
        self,
        strategy: RerankStrategy = RerankStrategy.WORD_COUNT,
        word_count_threshold: int = 3,
        confidence_threshold: float = 0.6,
        top_k: int = 10,
        max_candidates: int = 50,
    ):
        self.strategy = strategy
        self.word_count_threshold = word_count_threshold
        self.confidence_threshold = confidence_threshold
        self.top_k = top_k
        self.max_candidates = max_candidates


async def should_rerank(
    query: str,
    top_score: Optional[float],
    config: RerankConfig,
) -> bool:
    """
    Determine if reranking should be applied based on strategy.
    
    Args:
        query: Search query
        top_score: Highest score from hybrid search (or None)
        config: Rerank configuration
    
    Returns:
        True if reranking should be applied
    """
    if config.strategy == RerankStrategy.NEVER:
        return False
    
    if config.strategy == RerankStrategy.ALWAYS:
        return True
    
    if config.strategy == RerankStrategy.WORD_COUNT:
        word_count = len(query.split())
        return word_count >= config.word_count_threshold
    
    if config.strategy == RerankStrategy.CONFIDENCE:
        if top_score is None:
            return True  # No score available, rerank to be safe
        return top_score < config.confidence_threshold
    
    return False


async def rerank_results(
    query: str,
    documents: list[dict],
    top_k: int = 10,
    timeout: float = 5.0,
) -> list[dict]:
    """
    Rerank search results using Cohere Rerank API.
    
    Args:
        query: Search query
        documents: List of dicts with at least 'id' and 'name' keys
        top_k: Number of top results to return
        timeout: HTTP timeout in seconds
    
    Returns:
        Reranked list of documents (original dicts, reordered)
        Falls back to original order on error
    
    Raises:
        Exception on API errors (caller should handle)
    """
    api_key = getattr(settings, "cohere_api_key", "") or ""
    if not api_key:
        logger.warning("COHERE_API_KEY not configured, skipping rerank")
        return documents[:top_k]
    
    if not documents:
        return []
    
    # Prepare documents for Rerank API
    # We'll send the food name as the text to rank
    rerank_docs = [{"text": doc["name"]} for doc in documents]
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                RERANK_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": RERANK_MODEL,
                    "query": query,
                    "documents": rerank_docs,
                    "top_n": min(top_k, len(documents)),
                    "return_documents": False,  # We already have them
                },
            )
            
            if resp.status_code == 429:
                logger.warning("Cohere Rerank rate limit hit, using original order")
                return documents[:top_k]
            
            resp.raise_for_status()
            data = resp.json()
            
            # Rerank API returns results ordered by relevance with original index
            results = data.get("results", [])
            
            # Reorder documents based on Rerank results
            reranked = []
            for result in results:
                idx = result["index"]
                doc = documents[idx].copy()
                doc["rerank_score"] = result.get("relevance_score", 0.0)
                reranked.append(doc)
            
            logger.info(
                f"Reranked {len(documents)} candidates to {len(reranked)} results "
                f"for query '{query}'"
            )
            
            return reranked
            
    except Exception as e:
        logger.error(f"Rerank failed for query '{query}': {e}")
        # Fallback to original order
        return documents[:top_k]


async def rerank_food_matches(
    query: str,
    matches: list[dict],
    config: Optional[RerankConfig] = None,
) -> tuple[list[dict], bool]:
    """
    Conditionally rerank food search matches based on strategy.
    
    Args:
        query: Search query
        matches: List of food match dicts (from hybrid search)
        config: Rerank configuration (uses config.toml defaults if None)
    
    Returns:
        Tuple of (possibly reranked matches, was_reranked boolean)
    """
    if config is None:
        # Load from config.toml
        rerank_cfg = app_config.get("search", {}).get("rerank", {})
        config = RerankConfig(
            strategy=RerankStrategy(rerank_cfg.get("strategy", "word_count")),
            word_count_threshold=rerank_cfg.get("word_threshold", 3),
            confidence_threshold=rerank_cfg.get("confidence_threshold", 0.6),
            top_k=rerank_cfg.get("top_k", 10),
            max_candidates=rerank_cfg.get("max_candidates", 50),
        )
    
    # Check if we should rerank
    top_score = matches[0].get("similarity_score") if matches else None
    if not await should_rerank(query, top_score, config):
        logger.debug(f"Skipping rerank for '{query}' (strategy: {config.strategy})")
        return matches, False
    
    # Prepare candidates (limit to max_candidates)
    candidates = matches[: config.max_candidates]
    
    # Rerank
    try:
        reranked = await rerank_results(query, candidates, top_k=config.top_k)
        logger.info(
            f"Reranked '{query}': strategy={config.strategy}, "
            f"top_score={top_score:.3f if top_score else 'N/A'}"
        )
        return reranked, True
    except Exception as e:
        logger.error(f"Rerank error for '{query}': {e}, using original order")
        return matches, False
