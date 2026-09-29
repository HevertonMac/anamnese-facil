"""Add infectoparasitario value to eixo_a_enum

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-28
"""
from __future__ import annotations
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE eixo_a_enum ADD VALUE IF NOT EXISTS 'infectoparasitario'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum type.
    pass
