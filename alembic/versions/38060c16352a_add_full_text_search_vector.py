"""add full text search vector

Revision ID: 38060c16352a
Revises: d6f84e4c44c0
Create Date: 2026-10-06 19:00:57.333633

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '38060c16352a'
down_revision: Union[str, Sequence[str], None] = 'd6f84e4c44c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass