#!/usr/bin/env python3
"""
View search performance analytics.

Usage:
    uv run scripts/search_stats.py stats      # Show current performance stats
    uv run scripts/search_stats.py optimize   # Suggest optimal weights
    uv run scripts/search_stats.py recent     # Show recent selections
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.database import engine
from whati8.models.search_selection import SearchSelection
from whati8.services.search_analytics import (
    get_search_performance_stats,
    suggest_optimal_weights,
)


async def show_stats():
    """Display search performance statistics."""
    async with AsyncSession(engine) as db:
        stats = await get_search_performance_stats(db)
        print("\n" + "=" * 60)
        print("SEARCH PERFORMANCE STATISTICS")
        print("=" * 60)
        print(json.dumps(stats, indent=2))


async def show_optimization():
    """Show weight optimization suggestions."""
    async with AsyncSession(engine) as db:
        result = await suggest_optimal_weights(db)
        print("\n" + "=" * 60)
        print("WEIGHT OPTIMIZATION ANALYSIS")
        print("=" * 60)
        print(json.dumps(result, indent=2))
        
        if "recommended" in result:
            current = result["all_tested"][2]  # 0.5/0.5
            recommended = result["recommended"]
            
            print("\n" + "-" * 60)
            print("RECOMMENDATION:")
            print(f"  Current: {current['keyword_weight']:.1f} keyword / {current['semantic_weight']:.1f} semantic")
            print(f"  Optimal: {recommended['keyword_weight']:.1f} keyword / {recommended['semantic_weight']:.1f} semantic")
            print(f"  Improvement: {result['improvement_vs_current']:.2f}%")


async def show_recent(limit=20):
    """Show recent search selections."""
    async with AsyncSession(engine) as db:
        stmt = (
            select(SearchSelection)
            .order_by(SearchSelection.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        selections = result.scalars().all()
        
        print("\n" + "=" * 80)
        print(f"RECENT SEARCH SELECTIONS (last {limit})")
        print("=" * 80)
        
        for sel in selections:
            print(f"\n[{sel.created_at.strftime('%Y-%m-%d %H:%M:%S')}]")
            print(f"  Query: '{sel.query}'")
            print(f"  Selected: Food ID {sel.selected_food_id}")
            print(f"  Ranks: Trigram #{sel.trigram_rank}, Semantic #{sel.semantic_rank}, Hybrid #{sel.hybrid_rank}")
            if sel.hybrid_score:
                print(f"  Scores: T={sel.trigram_score:.3f}, S={sel.semantic_score:.3f}, H={sel.hybrid_score:.3f}")


async def main():
    parser = argparse.ArgumentParser(description="Search analytics tool")
    parser.add_argument(
        "command",
        choices=["stats", "optimize", "recent"],
        help="Command to run",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Limit for recent selections (default: 20)",
    )
    
    args = parser.parse_args()
    
    if args.command == "stats":
        await show_stats()
    elif args.command == "optimize":
        await show_optimization()
    elif args.command == "recent":
        await show_recent(args.limit)


if __name__ == "__main__":
    asyncio.run(main())
