"""Search analytics and selection logging."""

from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.database import engine
from whati8.models.search_selection import SearchSelection
from whati8.services.embedding_service import embed_query, EmbeddingProvider


async def log_search_selection(
    query: str,
    selected_food_id: int,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
    db: Optional[AsyncSession] = None,
) -> None:
    """
    Log a user's food selection and compute its ranking in each search method.
    
    This runs all three search methods (trigram, semantic, hybrid) in the background
    to determine where the selected food ranked in each result set.
    
    Args:
        query: The search query the user entered
        selected_food_id: The food ID the user selected
        user_id: User ID (if authenticated)
        session_id: Session ID for anonymous tracking
        db: Database session (will create one if not provided)
    """
    should_close = False
    if db is None:
        should_close = True
        db = AsyncSession(engine)
    
    try:
        # Get rankings and scores for the selected food in each method
        rankings = await _get_food_rankings(query, selected_food_id, db)
        
        # Insert log entry
        log_entry = SearchSelection(
            user_id=user_id,
            session_id=session_id,
            query=query,
            selected_food_id=selected_food_id,
            trigram_rank=rankings.get("trigram_rank"),
            semantic_rank=rankings.get("semantic_rank"),
            hybrid_rank=rankings.get("hybrid_rank"),
            trigram_score=rankings.get("trigram_score"),
            semantic_score=rankings.get("semantic_score"),
            hybrid_score=rankings.get("hybrid_score"),
        )
        
        db.add(log_entry)
        await db.commit()
        
    finally:
        if should_close:
            await db.close()


async def _get_food_rankings(
    query: str,
    food_id: int,
    db: AsyncSession,
    max_rank: int = 50,
) -> dict:
    """
    Compute where a specific food ranks in each search method.
    
    Returns dict with keys: trigram_rank, semantic_rank, hybrid_rank,
    and corresponding _score keys. Ranks are 1-indexed (1 = top result).
    NULL if not in top max_rank results.
    """
    result = {}
    
    # TRIGRAM ranking
    trigram_sql = text(f"""
        SELECT id, similarity(name, :query) AS score,
               ROW_NUMBER() OVER (ORDER BY similarity(name, :query) DESC) AS rank
        FROM foods
        WHERE similarity(name, :query) > 0.05
        LIMIT {max_rank}
    """)
    
    trigram_result = await db.execute(trigram_sql, {"query": query})
    for row in trigram_result.fetchall():
        if row[0] == food_id:
            result["trigram_rank"] = row[2]
            result["trigram_score"] = float(row[1])
            break
    
    # SEMANTIC ranking
    try:
        query_vec, provider = await embed_query(query)
        vec_str = "[" + ",".join(f"{v:.8f}" for v in query_vec) + "]"
        embedding_col = (
            "embedding_cohere" if provider == EmbeddingProvider.COHERE else "embedding_ollama"
        )
        
        semantic_sql = text(f"""
            SELECT id, 
                   1 - ({embedding_col} <=> '{vec_str}'::vector) AS score,
                   ROW_NUMBER() OVER (ORDER BY 1 - ({embedding_col} <=> '{vec_str}'::vector) DESC) AS rank
            FROM foods
            WHERE {embedding_col} IS NOT NULL
            LIMIT {max_rank}
        """)
        
        semantic_result = await db.execute(semantic_sql)
        for row in semantic_result.fetchall():
            if row[0] == food_id:
                result["semantic_rank"] = row[2]
                result["semantic_score"] = float(row[1])
                break
        
        # HYBRID ranking (0.5 keyword + 0.5 semantic)
        hybrid_sql = text(f"""
            SELECT id,
                   (0.5 * similarity(name, :query) + 0.5 * (1 - ({embedding_col} <=> '{vec_str}'::vector))) AS score,
                   ROW_NUMBER() OVER (
                       ORDER BY (0.5 * similarity(name, :query) + 0.5 * (1 - ({embedding_col} <=> '{vec_str}'::vector))) DESC
                   ) AS rank
            FROM foods
            WHERE {embedding_col} IS NOT NULL
            LIMIT {max_rank}
        """)
        
        hybrid_result = await db.execute(hybrid_sql, {"query": query})
        for row in hybrid_result.fetchall():
            if row[0] == food_id:
                result["hybrid_rank"] = row[2]
                result["hybrid_score"] = float(row[1])
                break
                
    except Exception:
        # If semantic search fails, just log trigram data
        pass
    
    return result


async def get_search_performance_stats(
    db: AsyncSession,
    min_selections: int = 10,
) -> dict:
    """
    Analyze search performance across all logged selections.
    
    Returns metrics like:
    - Average rank for each method
    - % of selections in top 1/3/5/10
    - Which method wins most often
    
    Args:
        db: Database session
        min_selections: Minimum number of selections required to return stats
    
    Returns:
        Dict with performance metrics
    """
    # Count total selections
    count_result = await db.execute(
        select(func.count(SearchSelection.id))
    )
    total = count_result.scalar()
    
    if total < min_selections:
        return {
            "total_selections": total,
            "message": f"Need at least {min_selections} selections for stats (have {total})"
        }
    
    # Get all selection data
    stmt = select(
        SearchSelection.trigram_rank,
        SearchSelection.semantic_rank,
        SearchSelection.hybrid_rank,
    ).where(SearchSelection.hybrid_rank.isnot(None))
    
    result = await db.execute(stmt)
    rows = result.fetchall()
    
    # Calculate stats
    trigram_ranks = [r[0] for r in rows if r[0] is not None]
    semantic_ranks = [r[1] for r in rows if r[1] is not None]
    hybrid_ranks = [r[2] for r in rows if r[2] is not None]
    
    def calc_metrics(ranks, name):
        if not ranks:
            return None
        return {
            "method": name,
            "avg_rank": sum(ranks) / len(ranks),
            "median_rank": sorted(ranks)[len(ranks) // 2],
            "top_1_pct": sum(1 for r in ranks if r == 1) / len(ranks) * 100,
            "top_3_pct": sum(1 for r in ranks if r <= 3) / len(ranks) * 100,
            "top_5_pct": sum(1 for r in ranks if r <= 5) / len(ranks) * 100,
            "top_10_pct": sum(1 for r in ranks if r <= 10) / len(ranks) * 100,
        }
    
    return {
        "total_selections": total,
        "trigram": calc_metrics(trigram_ranks, "trigram"),
        "semantic": calc_metrics(semantic_ranks, "semantic"),
        "hybrid": calc_metrics(hybrid_ranks, "hybrid"),
    }


async def suggest_optimal_weights(
    db: AsyncSession,
    min_selections: int = 50,
) -> dict:
    """
    Suggest optimal keyword/semantic weights based on logged selections.
    
    Tests different weight combinations (0.3/0.7, 0.4/0.6, 0.5/0.5, 0.6/0.4, 0.7/0.3)
    and recommends the one that minimizes average rank of selected foods.
    
    Returns:
        Dict with recommended weights and performance comparison
    """
    # Get all logged selections with scores
    stmt = select(
        SearchSelection.trigram_score,
        SearchSelection.semantic_score,
    ).where(
        SearchSelection.trigram_score.isnot(None),
        SearchSelection.semantic_score.isnot(None),
    )
    
    result = await db.execute(stmt)
    rows = result.fetchall()
    
    if len(rows) < min_selections:
        return {
            "message": f"Need {min_selections} selections with both scores (have {len(rows)})"
        }
    
    # Test different weight combinations
    weight_tests = [
        (0.7, 0.3),  # Keyword-heavy
        (0.6, 0.4),
        (0.5, 0.5),  # Current default
        (0.4, 0.6),
        (0.3, 0.7),  # Semantic-heavy
    ]
    
    results = []
    for kw_weight, sem_weight in weight_tests:
        # Compute hybrid scores with these weights
        scores = [
            kw_weight * row[0] + sem_weight * row[1]
            for row in rows
        ]
        avg_score = sum(scores) / len(scores)
        
        results.append({
            "keyword_weight": kw_weight,
            "semantic_weight": sem_weight,
            "avg_selected_score": avg_score,
        })
    
    # Find best weights (highest average score)
    best = max(results, key=lambda x: x["avg_selected_score"])
    
    return {
        "total_selections": len(rows),
        "recommended": best,
        "all_tested": results,
        "improvement_vs_current": (
            best["avg_selected_score"] - results[2]["avg_selected_score"]
        ) / results[2]["avg_selected_score"] * 100,
    }
