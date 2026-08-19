"""add start_byte and end_byte to chunks

Revision ID: b7dc960a98fb
Revises: 0001_initial_schema
Create Date: 2026-07-20 18:52:02.836192

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7dc960a98fb'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('code_chunks', sa.Column('start_byte', sa.Integer(), nullable=True))
    op.add_column('code_chunks', sa.Column('end_byte', sa.Integer(), nullable=True))

def downgrade() -> None:
    op.drop_column('code_chunks', 'end_byte')
    op.drop_column('code_chunks', 'start_byte')
