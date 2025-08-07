"""Add CASCADE delete to result.submission_id foreign key

Revision ID: f27d9935d937
Revises: 6ce231dda7ba
Create Date: 2025-08-04 09:48:27.143000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f27d9935d937'
down_revision: Union[str, Sequence[str], None] = '6ce231dda7ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the existing foreign key constraint
    op.drop_constraint('result_submission_id_fkey', 'result', type_='foreignkey')
    # Create new foreign key constraint with CASCADE delete
    op.create_foreign_key('result_submission_id_fkey', 'result', 'submission', ['submission_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the CASCADE foreign key constraint
    op.drop_constraint('result_submission_id_fkey', 'result', type_='foreignkey')
    # Restore the original foreign key constraint without CASCADE
    op.create_foreign_key('result_submission_id_fkey', 'result', 'submission', ['submission_id'], ['id'])
