"""sync sandbox_jobs columns with the SandboxJob ORM model

Revision ID: 9f3c2a1d5e40
Revises: b7dc960a98fb
Create Date: 2026-08-04 00:00:01.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9f3c2a1d5e40'
down_revision: Union[str, None] = 'b7dc960a98fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sandbox_jobs', sa.Column('worktree_path', sa.Text(), nullable=True))
    op.add_column(
        'sandbox_jobs',
        sa.Column('code_edits', postgresql.JSONB(astext_type=sa.Text()),
                  server_default='[]', nullable=False),
    )
    op.add_column('sandbox_jobs', sa.Column('test_command', sa.Text(), nullable=True))
    op.add_column('sandbox_jobs', sa.Column('exit_code', sa.Integer(), nullable=True))
    op.add_column(
        'sandbox_jobs',
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('sandbox_jobs', 'started_at')
    op.drop_column('sandbox_jobs', 'exit_code')
    op.drop_column('sandbox_jobs', 'test_command')
    op.drop_column('sandbox_jobs', 'code_edits')
    op.drop_column('sandbox_jobs', 'worktree_path')
