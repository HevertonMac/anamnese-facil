"""Initial schema with pgvector

Revision ID: 0001
Revises: 
Create Date: 2026-09-22
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Enums
    for enum_sql in [
        "CREATE TYPE eixo_a_enum AS ENUM ('cardiovascular','respiratorio','gastrointestinal','neurologico','musculoesqueletico','endocrino_metabolico','geniturinario')",
        "CREATE TYPE eixo_b_enum AS ENUM ('colaborativo','ansioso','resistente','confuso','minimizador')",
        "CREATE TYPE eixo_c_enum AS ENUM ('baixo_letramento_vulneravel','alto_letramento_bom_acesso','medio_letramento_media','pediatrico')",
        "CREATE TYPE complexidade_enum AS ENUM ('baixa','media','alta')",
        "CREATE TYPE sexo_enum AS ENUM ('M','F')",
    ]:
        op.execute(f"DO $$ BEGIN {enum_sql}; EXCEPTION WHEN duplicate_object THEN NULL; END $$;")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="student"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "virtual_patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("case_number", sa.Integer, nullable=False, unique=True),
        sa.Column("eixo_a", sa.Enum(name="eixo_a_enum", create_type=False), nullable=False),
        sa.Column("eixo_b", sa.Enum(name="eixo_b_enum", create_type=False), nullable=False),
        sa.Column("eixo_c", sa.Enum(name="eixo_c_enum", create_type=False), nullable=False),
        sa.Column("complexidade", sa.Enum(name="complexidade_enum", create_type=False), nullable=False),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("idade", sa.Integer, nullable=False),
        sa.Column("sexo", sa.Enum(name="sexo_enum", create_type=False), nullable=False),
        sa.Column("queixa_principal", sa.Text, nullable=False),
        sa.Column("diagnostico_principal", sa.String(200), nullable=False),
        sa.Column("case_data", postgresql.JSONB, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # knowledge_chunks with Vector column created via raw SQL for pgvector compatibility
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("virtual_patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section", sa.String(100), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("patient_id", "section", "chunk_index", name="uq_chunk_position"),
    )
    # Add vector column separately (pgvector type)
    op.execute(f"ALTER TABLE knowledge_chunks ADD COLUMN embedding vector({EMBEDDING_DIM})")

    op.create_table(
        "simulation_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("virtual_patients.id"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("simulation_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "evaluation_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("simulation_sessions.id"), unique=True, nullable=False),
        sa.Column("score_overall", sa.Float, nullable=True),
        sa.Column("score_identificacao", sa.Float, nullable=True),
        sa.Column("score_hda", sa.Float, nullable=True),
        sa.Column("score_antecedentes", sa.Float, nullable=True),
        sa.Column("score_sistemico", sa.Float, nullable=True),
        sa.Column("evaluation_data", postgresql.JSONB, nullable=True),
        sa.Column("feedback_text", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Indexes
    op.execute("CREATE INDEX idx_chunks_embedding ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50)")
    op.create_index("idx_patients_eixo_a", "virtual_patients", ["eixo_a"])
    op.create_index("idx_patients_complexidade", "virtual_patients", ["complexidade"])
    op.create_index("idx_chunks_patient", "knowledge_chunks", ["patient_id"])
    op.create_index("idx_chunks_section", "knowledge_chunks", ["section"])
    op.create_index("idx_messages_session", "conversation_messages", ["session_id"])


def downgrade() -> None:
    for table in ["evaluation_reports", "conversation_messages", "simulation_sessions", "knowledge_chunks", "virtual_patients", "users"]:
        op.drop_table(table)
    for enum in ["eixo_a_enum", "eixo_b_enum", "eixo_c_enum", "complexidade_enum", "sexo_enum"]:
        op.execute(f"DROP TYPE IF EXISTS {enum}")
