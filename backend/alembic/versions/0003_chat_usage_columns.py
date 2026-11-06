"""Add LLM usage columns to conversation_messages

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-06
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversation_messages", sa.Column("prompt_tokens", sa.Integer(), nullable=True))
    op.add_column("conversation_messages", sa.Column("completion_tokens", sa.Integer(), nullable=True))
    op.add_column("conversation_messages", sa.Column("model", sa.String(100), nullable=True))
    op.add_column("conversation_messages", sa.Column("provider", sa.String(30), nullable=True))
    op.add_column("conversation_messages", sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True))
    op.create_index("ix_conversation_messages_session_created", "conversation_messages", ["session_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_conversation_messages_session_created", table_name="conversation_messages")
    for col in ("cost_usd", "provider", "model", "completion_tokens", "prompt_tokens"):
        op.drop_column("conversation_messages", col)
