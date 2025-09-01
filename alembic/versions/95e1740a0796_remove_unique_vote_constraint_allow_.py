"""remove_unique_vote_constraint_allow_multiple_votes

Revision ID: 95e1740a0796
Revises: 292c44833495
Create Date: 2025-09-01 15:25:24.017036

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '95e1740a0796'
down_revision: Union[str, Sequence[str], None] = '292c44833495'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove unique constraint to allow multiple votes per user per model"""
    # Drop the unique constraint that prevents multiple votes
    op.drop_constraint('unique_user_model_vote', 'vote', type_='unique')


def downgrade() -> None:
    """Re-add unique constraint (note: this may fail if multiple votes exist)"""
    # Re-add the unique constraint
    op.create_unique_constraint('unique_user_model_vote', 'vote', ['user_id', 'model_version_id'])
