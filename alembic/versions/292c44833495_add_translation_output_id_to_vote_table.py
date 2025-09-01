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
    # Add translation_output_id column to vote table
    op.add_column('vote', sa.Column('translation_output_id', postgresql.UUID(as_uuid=True), nullable=True))
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_vote_translation_output', 
        'vote', 
        'translation_output', 
        ['translation_output_id'], 
        ['id'], 
        ondelete='SET NULL'
    )
    
    # Create index for better performance
    op.create_index('idx_vote_translation_output_id', 'vote', ['translation_output_id'])


def downgrade() -> None:
    """Remove translation_output_id column from vote table."""
    # Drop index
    op.drop_index('idx_vote_translation_output_id', 'vote')
    
    # Drop foreign key constraint
    op.drop_constraint('fk_vote_translation_output', 'vote', type_='foreignkey')
    
    # Drop column
    op.drop_column('vote', 'translation_output_id')
