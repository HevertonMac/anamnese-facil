"""Add chat context (provider, model, temperature, system prompt) to simulation_sessions

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-12
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("simulation_sessions", sa.Column("provider", sa.String(30), nullable=True))
    op.add_column("simulation_sessions", sa.Column("model", sa.String(100), nullable=True))
    op.add_column("simulation_sessions", sa.Column("temperature", sa.Float(), nullable=True))
    op.add_column("simulation_sessions", sa.Column("system_prompt", sa.Text(), nullable=True))
    op.create_index("ix_conversation_messages_session_created", "conversation_messages", ["session_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_conversation_messages_session_created", table_name="conversation_messages")
    for col in ("system_prompt", "temperature", "model", "provider"):
        op.drop_column("simulation_sessions", col)
