"""Add latency_ms to conversation_messages

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-06
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversation_messages", sa.Column("latency_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("conversation_messages", "latency_ms")
