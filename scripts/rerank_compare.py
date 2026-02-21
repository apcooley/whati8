#!/usr/bin/env python3
"""
Compare rerank vs hybrid-only performance.

Usage:
    uv run scripts/rerank_compare.py           # Show comparison stats
    uv run scripts/rerank_compare.py --detail  # Show per-query breakdown
"""

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.database import engine
from whati8.models.search_selection import SearchSelection


async def compare_performance(show_detail=False):
    """Compare rerank vs hybrid-only search performance."""
    async with AsyncSession(engine) as db:
        # Get selections where rerank was used
        stmt = (
            select(SearchSelection)
            .where(SearchSelection.rerank_used)
            .where(SearchSelection.hybrid_rank.isnot(None))
            .where(SearchSelection.rerank_rank.isnot(None))
        )
        result = await db.execute(stmt)
        selections = result.scalars().all()
        
        if not selections:
            print("\n❌ No reranked selections found yet.")
            print("   Make some searches with reranking enabled to see comparison.")
            return
        
        # Calculate metrics
        hybrid_better = 0
        rerank_better = 0
        tied = 0
        hybrid_ranks = []
        rerank_ranks = []
        improvements = []
        
        for sel in selections:
            hybrid_ranks.append(sel.hybrid_rank)
            rerank_ranks.append(sel.rerank_rank)
            
            if sel.rerank_rank < sel.hybrid_rank:
                rerank_better += 1
                improvements.append(sel.hybrid_rank - sel.rerank_rank)
            elif sel.hybrid_rank < sel.rerank_rank:
                hybrid_better += 1
                improvements.append(sel.hybrid_rank - sel.rerank_rank)
            else:
                tied += 1
                improvements.append(0)
            
            if show_detail:
                direction = "🟢" if sel.rerank_rank < sel.hybrid_rank else "🔴" if sel.hybrid_rank < sel.rerank_rank else "⚪"
                print(
                    f"\n{direction} '{sel.query}' → Food #{sel.selected_food_id}"
                )
                print(f"   Hybrid: #{sel.hybrid_rank} (score: {sel.hybrid_score:.3f})")
                print(f"   Rerank: #{sel.rerank_rank} (score: {sel.rerank_score:.3f})")
        
        # Summary stats
        total = len(selections)
        avg_hybrid = sum(hybrid_ranks) / total
        avg_rerank = sum(rerank_ranks) / total
        avg_improvement = sum(improvements) / total
        
        print("\n" + "=" * 70)
        print("RERANK vs HYBRID-ONLY COMPARISON")
        print("=" * 70)
        print(f"\nTotal selections analyzed: {total}")
        print("\n📊 Average Rankings:")
        print(f"   Hybrid-only:  #{avg_hybrid:.2f}")
        print(f"   With rerank:  #{avg_rerank:.2f}")
        print(f"   Improvement:  {avg_improvement:+.2f} positions")
        
        print("\n🏆 Head-to-Head:")
        print(f"   Rerank better: {rerank_better} ({rerank_better/total*100:.1f}%)")
        print(f"   Hybrid better: {hybrid_better} ({hybrid_better/total*100:.1f}%)")
        print(f"   Tied:          {tied} ({tied/total*100:.1f}%)")
        
        # Top-N metrics
        h_top1 = sum(1 for r in hybrid_ranks if r == 1)
        r_top1 = sum(1 for r in rerank_ranks if r == 1)
        h_top3 = sum(1 for r in hybrid_ranks if r <= 3)
        r_top3 = sum(1 for r in rerank_ranks if r <= 3)
        h_top5 = sum(1 for r in hybrid_ranks if r <= 5)
        r_top5 = sum(1 for r in rerank_ranks if r <= 5)
        
        print("\n📈 Top-N Performance:")
        print(f"   Top 1:  Hybrid {h_top1}/{total} ({h_top1/total*100:.1f}%)  |  Rerank {r_top1}/{total} ({r_top1/total*100:.1f}%)")
        print(f"   Top 3:  Hybrid {h_top3}/{total} ({h_top3/total*100:.1f}%)  |  Rerank {r_top3}/{total} ({r_top3/total*100:.1f}%)")
        print(f"   Top 5:  Hybrid {h_top5}/{total} ({h_top5/total*100:.1f}%)  |  Rerank {r_top5}/{total} ({r_top5/total*100:.1f}%)")
        
        # Recommendation
        print("\n💡 Recommendation:")
        if avg_improvement > 0.5:
            print(f"   ✅ Rerank is IMPROVING results by {avg_improvement:.1f} positions on average")
            print("   Keep reranking enabled for better search quality.")
        elif avg_improvement < -0.5:
            print(f"   ⚠️  Hybrid-only is BETTER by {-avg_improvement:.1f} positions on average")
            print("   Consider disabling rerank or adjusting trigger strategy.")
        else:
            print("   ⚪ Results are roughly equivalent (±0.5 positions)")
            print("   Use hybrid-only to save API costs unless quality matters more.")


async def main():
    parser = argparse.ArgumentParser(description="Compare rerank vs hybrid performance")
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Show per-query breakdown",
    )
    args = parser.parse_args()
    
    await compare_performance(show_detail=args.detail)


if __name__ == "__main__":
    asyncio.run(main())
