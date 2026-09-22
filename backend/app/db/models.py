"""
SQLAlchemy models for Anamnese Fácil platform.
Uses pgvector for semantic search on clinical knowledge chunks.
"""
from __future__ import annotations

import uuid
import enum
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class EixoA(str, enum.Enum):
    cardiovascular = "cardiovascular"
    respiratorio = "respiratorio"
    gastrointestinal = "gastrointestinal"
    neurologico = "neurologico"
    musculoesqueletico = "musculoesqueletico"
    endocrino_metabolico = "endocrino_metabolico"
    geniturinario = "geniturinario"


class EixoB(str, enum.Enum):
    colaborativo = "colaborativo"
    ansioso = "ansioso"
    resistente = "resistente"
    confuso = "confuso"
    minimizador = "minimizador"


class EixoC(str, enum.Enum):
    baixo_letramento_vulneravel = "baixo_letramento_vulneravel"
    alto_letramento_bom_acesso = "alto_letramento_bom_acesso"
    medio_letramento_media = "medio_letramento_media"
    pediatrico = "pediatrico"


class ComplexidadeEnum(str, enum.Enum):
    baixa = "baixa"
    media = "media"
    alta = "alta"


class SexoEnum(str, enum.Enum):
    M = "M"
    F = "F"


class VirtualPatient(Base):
    """Core model for a virtual patient case."""
    __tablename__ = "virtual_patients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    eixo_a: Mapped[str] = mapped_column(Enum(EixoA, name="eixo_a_enum"), nullable=False)
    eixo_b: Mapped[str] = mapped_column(Enum(EixoB, name="eixo_b_enum"), nullable=False)
    eixo_c: Mapped[str] = mapped_column(Enum(EixoC, name="eixo_c_enum"), nullable=False)
    complexidade: Mapped[str] = mapped_column(Enum(ComplexidadeEnum, name="complexidade_enum"), nullable=False)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    idade: Mapped[int] = mapped_column(Integer, nullable=False)
    sexo: Mapped[str] = mapped_column(Enum(SexoEnum, name="sexo_enum"), nullable=False)
    queixa_principal: Mapped[str] = mapped_column(Text, nullable=False)
    diagnostico_principal: Mapped[str] = mapped_column(String(200), nullable=False)
    case_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    knowledge_chunks: Mapped[list["KnowledgeChunk"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    simulation_sessions: Mapped[list["SimulationSession"]] = relationship(back_populates="patient")


class KnowledgeChunk(Base):
    """Chunked text from clinical cases, stored with embeddings for RAG."""
    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("virtual_patients.id", ondelete="CASCADE"))
    section: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(1536), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    patient: Mapped[VirtualPatient] = relationship(back_populates="knowledge_chunks")

    __table_args__ = (
        UniqueConstraint("patient_id", "section", "chunk_index", name="uq_chunk_position"),
    )


class User(Base):
    """Platform user (student or instructor)."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="student")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    simulation_sessions: Mapped[list["SimulationSession"]] = relationship(back_populates="student")


class SimulationSession(Base):
    """A student's anamnesis simulation session with a virtual patient."""
    __tablename__ = "simulation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("virtual_patients.id"))
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped[VirtualPatient] = relationship(back_populates="simulation_sessions")
    student: Mapped[User] = relationship(back_populates="simulation_sessions")
    messages: Mapped[list["ConversationMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    evaluation: Mapped[Optional["EvaluationReport"]] = relationship(back_populates="session", uselist=False)


class ConversationMessage(Base):
    """Individual message in a simulation conversation."""
    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulation_sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[SimulationSession] = relationship(back_populates="messages")


class EvaluationReport(Base):
    """Automated evaluation of a completed simulation session."""
    __tablename__ = "evaluation_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulation_sessions.id"), unique=True)
    score_overall: Mapped[Optional[float]] = mapped_column(nullable=True)
    score_identificacao: Mapped[Optional[float]] = mapped_column(nullable=True)
    score_hda: Mapped[Optional[float]] = mapped_column(nullable=True)
    score_antecedentes: Mapped[Optional[float]] = mapped_column(nullable=True)
    score_sistemico: Mapped[Optional[float]] = mapped_column(nullable=True)
    evaluation_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[SimulationSession] = relationship(back_populates="evaluation")
