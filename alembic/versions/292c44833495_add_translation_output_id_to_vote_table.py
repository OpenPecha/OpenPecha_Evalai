"""add_translation_output_id_to_vote_table

Revision ID: 292c44833495
Revises: c7f8d9e5a2b1
Create Date: 2025-08-29 17:55:47.287014

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '292c44833495'
down_revision: Union[str, Sequence[str], None] = 'c7f8d9e5a2b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add translation_output_id column to vote table."""
    # NOTE: This migration is now a no-op because the translation_output_id column
    # and its foreign key constraint are created directly in the vote table creation
    # migration (c7f8d9e5a2b1_create_vote_table_5star_rating.py)
    pass


def downgrade() -> None:
    """Remove translation_output_id column from vote table."""
    # NOTE: This migration is now a no-op because the translation_output_id column
    # and its foreign key constraint are created directly in the vote table creation
    # migration (c7f8d9e5a2b1_create_vote_table_5star_rating.py)
    pass
