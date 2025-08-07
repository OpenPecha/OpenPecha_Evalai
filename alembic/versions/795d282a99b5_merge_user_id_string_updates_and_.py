"""Merge user_id string updates and challenge_id foreign key

Revision ID: 795d282a99b5
Revises: 172af7e46c02, fa97fa408ec6
Create Date: 2025-08-07 16:06:08.780247

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '795d282a99b5'
down_revision: Union[str, Sequence[str], None] = ('172af7e46c02', 'fa97fa408ec6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
