"""Add clinica_cirurgica and psiquiatria_saude_mental to eixo_a_enum; add eixo_a_secundario

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-12
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE eixo_a_enum ADD VALUE IF NOT EXISTS 'clinica_cirurgica'")
        op.execute("ALTER TYPE eixo_a_enum ADD VALUE IF NOT EXISTS 'psiquiatria_saude_mental'")
    op.add_column(
        "virtual_patients",
        sa.Column("eixo_a_secundario", postgresql.ENUM(name="eixo_a_enum", create_type=False), nullable=True),
    )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; only the column is dropped.
    op.drop_column("virtual_patients", "eixo_a_secundario")
