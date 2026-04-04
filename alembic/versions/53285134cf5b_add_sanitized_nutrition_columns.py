"""add_sanitized_nutrition_columns

Revision ID: 53285134cf5b
Revises: d5e6f7g8h9i0
Create Date: 2026-04-03 22:34:43.242846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '53285134cf5b'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7g8h9i0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add sanitized nutrition columns, tier, data_source, and metadata to foods table."""
    op.add_column('foods', sa.Column('tier', sa.SmallInteger(), nullable=True))
    op.add_column('foods', sa.Column('data_source', sa.String(length=50), nullable=True))
    op.add_column('foods', sa.Column('is_deprecated', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('foods', sa.Column('imported_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('foods', sa.Column('is_complete', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('foods', sa.Column('sanitized_base_grams', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('foods', sa.Column('sanitized_calories', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('foods', sa.Column('sanitized_protein', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('foods', sa.Column('sanitized_carbs', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('foods', sa.Column('sanitized_fat', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('foods', sa.Column('sanitized_fiber', sa.Numeric(precision=10, scale=2), nullable=True))
    op.create_index('ix_foods_data_source', 'foods', ['data_source'], unique=False)
    op.create_index('ix_foods_tier', 'foods', ['tier'], unique=False)


def downgrade() -> None:
    """Remove sanitized nutrition columns, tier, data_source, and metadata from foods table."""
    op.drop_index('ix_foods_tier', table_name='foods')
    op.drop_index('ix_foods_data_source', table_name='foods')
    op.drop_column('foods', 'sanitized_fiber')
    op.drop_column('foods', 'sanitized_fat')
    op.drop_column('foods', 'sanitized_carbs')
    op.drop_column('foods', 'sanitized_protein')
    op.drop_column('foods', 'sanitized_calories')
    op.drop_column('foods', 'sanitized_base_grams')
    op.drop_column('foods', 'is_complete')
    op.drop_column('foods', 'imported_at')
    op.drop_column('foods', 'is_deprecated')
    op.drop_column('foods', 'data_source')
    op.drop_column('foods', 'tier')
