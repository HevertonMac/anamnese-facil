"""Add chat context (provider, model, temperature, system prompt) to simulation_sessions

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-06
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("simulation_sessions", sa.Column("provider", sa.String(30), nullable=True))
    op.add_column("simulation_sessions", sa.Column("model", sa.String(100), nullable=True))
    op.add_column("simulation_sessions", sa.Column("temperature", sa.Float(), nullable=True))
    op.add_column("simulation_sessions", sa.Column("system_prompt", sa.Text(), nullable=True))
    op.add_column("simulation_sessions", sa.Column("system_prompt_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    for col in ("system_prompt_tokens", "system_prompt", "temperature", "model", "provider"):
        op.drop_column("simulation_sessions", col)
