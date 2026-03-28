"""Add pgvector extension and embedding columns to foods table.

Revision ID: a1b2c3d4e5f6
Revises: 6f00f447ddc
Create Date: 2026-02-20
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "6f00f447ddc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension (requires superuser or extension already available)
    # Note: This should be run as superuser first:
    #   sudo -u postgres psql -d whati8 -c "CREATE EXTENSION IF NOT EXISTS vector;"
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Add embedding columns as vector(768) type directly
    # Cohere embed-english-v3.0 (truncated from 1024 via Matryoshka)
    # Ollama nomic-embed-text (native 768)
    # SQLAlchemy doesn't natively support vector type, so use raw SQL
    op.execute("ALTER TABLE foods ADD COLUMN embedding_cohere vector(768)")
    op.execute("ALTER TABLE foods ADD COLUMN embedding_ollama vector(768)")

    # Create HNSW indexes for fast approximate nearest neighbor search
    # HNSW is preferred over IVFFlat for small datasets (<100K)
    op.execute(
        "CREATE INDEX ix_foods_embedding_cohere ON foods "
        "USING hnsw (embedding_cohere vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    op.execute(
        "CREATE INDEX ix_foods_embedding_ollama ON foods "
        "USING hnsw (embedding_ollama vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_foods_embedding_ollama")
    op.execute("DROP INDEX IF EXISTS ix_foods_embedding_cohere")
    op.drop_column("foods", "embedding_ollama")
    op.drop_column("foods", "embedding_cohere")
    # Don't drop the vector extension — other things might use it
