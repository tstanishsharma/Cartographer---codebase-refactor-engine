"""sync ORM models to database schema

Adds the columns the SandboxJob/AgentRun/ChatSession ORM models define
but the initial migration omitted. Without these, ORM cascade deletes
(session.delete(repository)) fail with UndefinedColumnError.

Revision ID: 02c3ec1a3c88
Revises: 9f3c2a1d5e40
Create Date: 2026-08-03 19:55:39.351527

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '02c3ec1a3c88'
down_revision: Union[str, None] = '9f3c2a1d5e40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'agent_runs',
        sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()),
                  server_default='[]', nullable=False),
    )
    op.add_column('agent_runs', sa.Column('error_message', sa.Text(), nullable=True))
    op.add_column(
        'chat_sessions',
        sa.Column('memory', postgresql.JSONB(astext_type=sa.Text()),
                  server_default='{}', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('chat_sessions', 'memory')
    op.drop_column('agent_runs', 'error_message')
    op.drop_column('agent_runs', 'citations')
