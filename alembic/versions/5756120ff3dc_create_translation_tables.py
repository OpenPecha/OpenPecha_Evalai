"""create_translation_tables

Revision ID: 5756120ff3dc
Revises: 292c44833495
Create Date: 2025-09-01 10:19:24.247154

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '5756120ff3dc'
down_revision: Union[str, Sequence[str], None] = 'd5b6695b16ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create translation_job and translation_output tables."""
    
    # Create translation_job table
    op.create_table('translation_job',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('source_text', sa.Text(), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id', name='translation_job_pkey'),
        sa.UniqueConstraint('id', name='translation_job_id_key')
    )
    
    # Create translation_output table
    op.create_table('translation_output',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_version_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('streamed_text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['job_id'], ['translation_job.id'], name='fk_translation_output_job'),
        sa.ForeignKeyConstraint(['model_version_id'], ['model_version.id'], name='fk_translation_output_model_version'),
        sa.PrimaryKeyConstraint('id', name='translation_output_pkey'),
        sa.UniqueConstraint('id', name='translation_output_id_key')
    )
    
    # Create indexes for better performance
    op.create_index('idx_translation_job_user_id', 'translation_job', ['user_id'])
    op.create_index('idx_translation_output_job_id', 'translation_output', ['job_id'])
    op.create_index('idx_translation_output_model_version_id', 'translation_output', ['model_version_id'])


def downgrade() -> None:
    """Drop translation tables."""
    # Drop indexes
    op.drop_index('idx_translation_output_model_version_id', 'translation_output')
    op.drop_index('idx_translation_output_job_id', 'translation_output')
    op.drop_index('idx_translation_job_user_id', 'translation_job')
    
    # Drop tables (order matters due to foreign keys)
    op.drop_table('translation_output')
    op.drop_table('translation_job')
