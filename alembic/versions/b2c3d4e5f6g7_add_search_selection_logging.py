"""Add search selection logging table

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-21
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6g7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create table to log which foods users select and how they ranked
    op.create_table(
        "search_selections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=True),  # FK to users if you have auth
        sa.Column("session_id", sa.String(255), nullable=True),  # Or session tracking
        sa.Column("query", sa.String(255), nullable=False),  # What they searched for
        sa.Column("selected_food_id", sa.Integer(), sa.ForeignKey("foods.id"), nullable=False),
        sa.Column("trigram_rank", sa.Integer(), nullable=True),  # Position in trigram results (1-indexed, NULL if not in top N)
        sa.Column("semantic_rank", sa.Integer(), nullable=True),  # Position in semantic results
        sa.Column("hybrid_rank", sa.Integer(), nullable=True),  # Position in hybrid results
        sa.Column("rerank_rank", sa.Integer(), nullable=True),  # Position in reranked results (if rerank was used)
        sa.Column("trigram_score", sa.Float(), nullable=True),  # Actual trigram similarity score
        sa.Column("semantic_score", sa.Float(), nullable=True),  # Actual semantic score
        sa.Column("hybrid_score", sa.Float(), nullable=True),  # Final hybrid score
        sa.Column("rerank_score", sa.Float(), nullable=True),  # Rerank relevance score (if rerank was used)
        sa.Column("rerank_used", sa.Boolean(), nullable=False, server_default="false"),  # Whether rerank was applied
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # Indexes for analytics queries
    op.create_index("ix_search_selections_query", "search_selections", ["query"])
    op.create_index("ix_search_selections_food_id", "search_selections", ["selected_food_id"])
    op.create_index("ix_search_selections_created_at", "search_selections", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_search_selections_created_at", table_name="search_selections")
    op.drop_index("ix_search_selections_food_id", table_name="search_selections")
    op.drop_index("ix_search_selections_query", table_name="search_selections")
    op.drop_table("search_selections")
