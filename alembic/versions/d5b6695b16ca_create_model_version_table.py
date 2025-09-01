"""create_model_version_table

Revision ID: d5b6695b16ca
Revises: 292c44833495
Create Date: 2025-09-01 10:15:19.751685

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd5b6695b16ca'
down_revision: Union[str, Sequence[str], None] = '157d00e2f04e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create model_version table."""
    # Create model_version table
    op.create_table('model_version',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('version', sa.String(), nullable=False, unique=True),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('vote_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id', name='model_version_pkey'),
        sa.UniqueConstraint('version', name='model_version_version_key')
    )
    
    # Create index for vote_count (for ordering by popularity)
    op.create_index('idx_model_version_vote_count', 'model_version', ['vote_count'])


def downgrade() -> None:
    """Drop model_version table."""
    # Drop indexes
    op.drop_index('idx_model_version_vote_count', 'model_version')
    
    # Drop table
    op.drop_table('model_version')
