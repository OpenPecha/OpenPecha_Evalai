"""create_vote_table_5star_rating

Revision ID: c7f8d9e5a2b1
Revises: 157d00e2f04e
Create Date: 2025-08-29 17:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c7f8d9e5a2b1'
down_revision: Union[str, Sequence[str], None] = '5756120ff3dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Create Vote table for 5-star rating system."""
    
    # Create vote table
    op.create_table('vote',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('model_version_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('translation_output_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Constraints
        sa.CheckConstraint('score >= 1 AND score <= 5', name='valid_score_range'),
        sa.UniqueConstraint('user_id', 'model_version_id', name='unique_user_model_vote'),
        sa.ForeignKeyConstraint(['model_version_id'], ['model_version.id'], name='fk_vote_model_version', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['translation_output_id'], ['translation_output.id'], name='fk_vote_translation_output', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name='vote_pkey')
    )
    
    # Create indexes for better performance
    op.create_index('idx_vote_user_id', 'vote', ['user_id'])
    op.create_index('idx_vote_model_version_id', 'vote', ['model_version_id'])
    op.create_index('idx_vote_score', 'vote', ['score'])
    op.create_index('idx_vote_created_at', 'vote', ['created_at'])
    op.create_index('idx_vote_translation_output_id', 'vote', ['translation_output_id'])


def downgrade() -> None:
    """Downgrade schema - Remove Vote table."""
    
    # Drop indexes
    op.drop_index('idx_vote_translation_output_id', 'vote')
    op.drop_index('idx_vote_created_at', 'vote')
    op.drop_index('idx_vote_score', 'vote')
    op.drop_index('idx_vote_model_version_id', 'vote')
    op.drop_index('idx_vote_user_id', 'vote')
    
    # Drop table
    op.drop_table('vote')
