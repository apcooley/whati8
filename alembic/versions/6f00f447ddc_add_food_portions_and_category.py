"""Add food_portions table and category column to foods

Revision ID: 6f00f447ddc
Revises: 0e7d46dcb3b4
Create Date: 2026-02-09 14:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6f00f447ddc"
down_revision: Union[str, Sequence[str], None] = "0e7d46dcb3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add category column to foods table
    op.add_column(
        "foods",
        sa.Column("category", sa.String(length=255), nullable=True),
    )
    op.create_index(
        op.f("ix_foods_category"),
        "foods",
        ["category"],
        unique=False,
    )

    # Create food_portions table
    op.create_table(
        "food_portions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("unit_name", sa.String(length=100), nullable=False),
        sa.Column("unit_abbreviation", sa.String(length=20), nullable=True),
        sa.Column("gram_weight", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("modifier", sa.String(length=100), nullable=True),
        sa.Column("portion_description", sa.Text(), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["food_id"],
            ["foods.id"],
            name=op.f("fk_food_portions_food_id_foods"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_food_portions")),
    )
    op.create_index(
        op.f("ix_food_portions_food_id"),
        "food_portions",
        ["food_id"],
        unique=False,
    )
    op.create_index(
        "ix_food_portions_sequence",
        "food_portions",
        ["food_id", "sequence_number"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_food_portions_sequence", table_name="food_portions")
    op.drop_index(
        op.f("ix_food_portions_food_id"),
        table_name="food_portions",
    )
    op.drop_table("food_portions")

    op.drop_index(
        op.f("ix_foods_category"),
        table_name="foods",
    )
    op.drop_column("foods", "category")
