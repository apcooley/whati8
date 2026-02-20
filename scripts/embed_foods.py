#!/usr/bin/env python3
"""
Pre-compute embeddings for all foods in the database.

Usage:
    uv run scripts/embed_foods.py                    # Embed with both providers
    uv run scripts/embed_foods.py --provider cohere   # Cohere only
    uv run scripts/embed_foods.py --provider ollama   # Ollama only
    uv run scripts/embed_foods.py --batch-size 50     # Custom batch size
    uv run scripts/embed_foods.py --missing-only       # Only embed foods without vectors
"""

import argparse
import asyncio
import time

from sqlalchemy import text

from whati8.database import engine
from whati8.services.embedding_service import (
    EMBEDDING_DIM,
    EmbeddingProvider,
    embed_corpus,
)


async def get_foods(missing_only: bool, provider: str | None) -> list[tuple[int, str]]:
    """Fetch food IDs and names from DB."""
    async with engine.connect() as conn:
        if missing_only and provider:
            col = f"embedding_{provider}"
            result = await conn.execute(
                text(f"SELECT id, name FROM foods WHERE {col} IS NULL ORDER BY id")
            )
        else:
            result = await conn.execute(text("SELECT id, name FROM foods ORDER BY id"))
        return [(row[0], row[1]) for row in result.fetchall()]


async def store_embeddings(
    food_ids: list[int],
    vectors: list[list[float]],
    column: str,
) -> int:
    """Store embedding vectors in the database."""
    async with engine.begin() as conn:
        updated = 0
        for food_id, vec in zip(food_ids, vectors):
            # Format as pgvector literal: [0.1,0.2,...]
            vec_str = "[" + ",".join(f"{v:.8f}" for v in vec) + "]"
            await conn.execute(
                text(f"UPDATE foods SET {column} = :vec::vector WHERE id = :id"),
                {"vec": vec_str, "id": food_id},
            )
            updated += 1
        return updated


async def embed_all(
    provider_name: str,
    batch_size: int,
    missing_only: bool,
) -> None:
    """Embed foods with a single provider."""
    provider = EmbeddingProvider(provider_name)
    column = f"embedding_{provider_name}"

    foods = await get_foods(missing_only, provider_name)
    if not foods:
        print(f"  [{provider_name}] No foods to embed.")
        return

    food_ids = [f[0] for f in foods]
    food_names = [f[1] for f in foods]

    print(f"  [{provider_name}] Embedding {len(foods)} foods in batches of {batch_size}...")
    t0 = time.time()

    for i in range(0, len(food_names), batch_size):
        batch_names = food_names[i : i + batch_size]
        batch_ids = food_ids[i : i + batch_size]

        try:
            vectors = await embed_corpus(batch_names, provider)
        except Exception as e:
            print(f"  [{provider_name}] FAILED at batch {i // batch_size + 1}: {e}")
            return

        if len(vectors) != len(batch_names):
            print(
                f"  [{provider_name}] Vector count mismatch: "
                f"got {len(vectors)}, expected {len(batch_names)}"
            )
            return

        # Validate dimensions
        for j, vec in enumerate(vectors):
            if len(vec) != EMBEDDING_DIM:
                print(
                    f"  [{provider_name}] Wrong dimension for food {batch_ids[j]}: "
                    f"got {len(vec)}, expected {EMBEDDING_DIM}"
                )
                return

        await store_embeddings(batch_ids, vectors, column)
        elapsed = time.time() - t0
        done = i + len(batch_names)
        rate = done / elapsed if elapsed > 0 else 0
        print(
            f"  [{provider_name}] {done}/{len(foods)} "
            f"({rate:.0f} foods/sec, {elapsed:.1f}s elapsed)"
        )

    elapsed = time.time() - t0
    print(f"  [{provider_name}] Done! {len(foods)} foods in {elapsed:.1f}s")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Embed all foods in the database")
    parser.add_argument(
        "--provider",
        choices=["cohere", "ollama"],
        help="Embed with a single provider (default: both)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size for embedding calls (default: 50)",
    )
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Only embed foods that don't have vectors yet",
    )
    args = parser.parse_args()

    providers = [args.provider] if args.provider else ["cohere", "ollama"]

    # Quick count
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT count(*) FROM foods"))
        total = result.scalar()
        print(f"Total foods in database: {total}")

    for p in providers:
        await embed_all(p, args.batch_size, args.missing_only)

    print("\n✅ Embedding complete!")


if __name__ == "__main__":
    asyncio.run(main())
