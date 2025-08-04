"""Add required challenge_id foreign key to submission

Revision ID: fa97fa408ec6
Revises: f27d9935d937
Create Date: 2025-08-04 16:34:56.465997

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'fa97fa408ec6'
down_revision: Union[str, Sequence[str], None] = 'f27d9935d937'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add challenge_id column to submission table
    op.add_column('submission', sa.Column('challenge_id', sa.UUID(), nullable=False))
    # Create index for challenge_id
    op.create_index(op.f('ix_submission_challenge_id'), 'submission', ['challenge_id'], unique=False)
    # Create foreign key constraint
    op.create_foreign_key('submission_challenge_id_fkey', 'submission', 'challenge', ['challenge_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop foreign key constraint
    op.drop_constraint('submission_challenge_id_fkey', 'submission', type_='foreignkey')
    # Drop index
    op.drop_index(op.f('ix_submission_challenge_id'), table_name='submission')
    # Drop challenge_id column
    op.drop_column('submission', 'challenge_id')
