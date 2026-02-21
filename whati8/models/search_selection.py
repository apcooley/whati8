"""Search selection logging model."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from whati8.database import Base


class SearchSelection(Base):
    """
    Log of user food selections from search results.
    
    Used to analyze which ranking method (trigram vs semantic vs hybrid)
    produces better results for users, enabling data-driven tuning of
    the hybrid search weights.
    """

    __tablename__ = "search_selections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True)  # For future auth integration
    session_id = Column(String(255), nullable=True)  # Session tracking
    
    query = Column(String(255), nullable=False, index=True)
    selected_food_id = Column(Integer, ForeignKey("foods.id"), nullable=False, index=True)
    
    # Rankings (1-indexed position, NULL if not in top N results)
    trigram_rank = Column(Integer, nullable=True)
    semantic_rank = Column(Integer, nullable=True)
    hybrid_rank = Column(Integer, nullable=True)
    
    # Scores (for analysis)
    trigram_score = Column(Float, nullable=True)
    semantic_score = Column(Float, nullable=True)
    hybrid_score = Column(Float, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    food = relationship("Food", backref="search_selections")
