"""Lógica do chat: sessões, histórico, chamada ao LLM."""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ConversationMessage, SimulationSession, User, VirtualPatient
from app.modules.chat import config
from app.modules.chat.llm.base import LLMError, LLMNotConfigured
from app.modules.chat.llm.factory import get_provider
from app.modules.chat.prompt import build_system_prompt

log = logging.getLogger(__name__)


async def create_session(
    db: AsyncSession, user: User, patient_id: uuid.UUID, model: str | None = None
) -> SimulationSession:
    provider = config.provider_name()
    if model is not None:
        if user.role != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Apenas administradores podem escolher o modelo")
        if provider != "openai" or model not in config.allowed_models():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Modelo não permitido: {model}")
    patient = await db.get(VirtualPatient, patient_id)
    if patient is None or not patient.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paciente não encontrado")
    system_prompt = build_system_prompt(patient.case_data)
    session = SimulationSession(
        patient_id=patient_id,
        student_id=user.id,
        status="active",
        provider=provider,
        model=model or config.model_name(provider),
        temperature=config.temperature(),
        system_prompt=system_prompt,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: uuid.UUID, user: User, *, with_messages: bool = False) -> SimulationSession:
    stmt = select(SimulationSession).where(SimulationSession.id == session_id)
    if with_messages:
        stmt = stmt.options(selectinload(SimulationSession.messages))
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sessão não encontrada")
    if session.student_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sessão pertence a outro usuário")
    return session


async def list_sessions(db: AsyncSession, user: User) -> list[SimulationSession]:
    stmt = (
        select(SimulationSession)
        .where(SimulationSession.student_id == user.id)
        .order_by(SimulationSession.started_at.desc())
        .limit(100)
    )
    return list((await db.execute(stmt)).scalars().all())


async def end_session(db: AsyncSession, session: SimulationSession) -> SimulationSession:
    if session.status != "ended":
        session.status = "ended"
        session.ended_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(session)
    return session


async def _count(db: AsyncSession, stmt) -> int:
    return int((await db.execute(stmt)).scalar() or 0)


async def _enforce_limits(db: AsyncSession, session: SimulationSession, user: User) -> None:
    total = await _count(
        db, select(func.count()).select_from(ConversationMessage).where(ConversationMessage.session_id == session.id)
    )
    if total >= config.max_messages_per_session():
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Limite de mensagens da sessão atingido. Encerre a sessão.")

    since = datetime.now(timezone.utc) - timedelta(minutes=1)
    recent = await _count(
        db,
        select(func.count())
        .select_from(ConversationMessage)
        .join(SimulationSession, SimulationSession.id == ConversationMessage.session_id)
        .where(
            SimulationSession.student_id == user.id,
            ConversationMessage.role == "user",
            ConversationMessage.created_at >= since,
        ),
    )
    if recent >= config.rate_limit_per_minute():
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Muitas mensagens em pouco tempo. Aguarde um instante.")


def _to_llm_messages(history: list[ConversationMessage], new_content: str) -> list[dict[str, str]]:
    msgs = [{"role": m.role, "content": m.content} for m in history]
    # Messages API da Anthropic exige começar por "user"; a janela pode cortar no meio de um par.
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    msgs.append({"role": "user", "content": new_content})
    return msgs


_LABEL_RE = re.compile(r"^\s*(paciente|assistente|assistant)\s*:\s*", re.IGNORECASE)


def clean_reply(text: str) -> str:
    """Remove vícios de chatbot que escapam do prompt: rótulo de falante, markdown e aspas externas."""
    text = _LABEL_RE.sub("", text.strip())
    text = re.sub(r"\*\*?|__|`", "", text)
    text = re.sub(r"^\s*[-•]\s+", "", text, flags=re.MULTILINE)
    if len(text) > 1 and text[0] == text[-1] == '"':
        text = text[1:-1]
    return text.strip()


async def send_message(
    db: AsyncSession, session: SimulationSession, user: User, content: str
) -> tuple[ConversationMessage, ConversationMessage]:
    content = content.strip()
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Mensagem vazia")
    if len(content) > config.max_message_chars():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Mensagem acima de {config.max_message_chars()} caracteres"
        )
    if session.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "Sessão encerrada")

    await _enforce_limits(db, session, user)

    # Prompt congelado na criação da sessão (conversa reproduzível); sessões antigas reconstroem do caso.
    system_prompt = session.system_prompt
    if not system_prompt:
        patient = await db.get(VirtualPatient, session.patient_id)
        if patient is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Paciente não encontrado")
        system_prompt = build_system_prompt(patient.case_data)

    hist_stmt = (
        select(ConversationMessage)
        .where(ConversationMessage.session_id == session.id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(config.max_history())
    )
    history = list(reversed((await db.execute(hist_stmt)).scalars().all()))

    try:
        result = await get_provider(session.provider, session.model).chat(
            system=system_prompt,
            messages=_to_llm_messages(history, content),
            max_tokens=config.max_output_tokens(),
            temperature=session.temperature if session.temperature is not None else config.temperature(),
        )
    except LLMNotConfigured as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))
    except LLMError as e:
        log.error(f"Falha no LLM do chat: {e}")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Falha ao obter resposta do paciente. Tente novamente.")

    # created_at explícito: as duas linhas entram na mesma transação e o now() do servidor seria igual.
    now = datetime.now(timezone.utc)
    user_msg = ConversationMessage(session_id=session.id, role="user", content=content, created_at=now)
    patient_msg = ConversationMessage(
        session_id=session.id,
        role="assistant",
        content=clean_reply(result.text),
        created_at=now + timedelta(milliseconds=1),
    )
    db.add(user_msg)
    db.add(patient_msg)
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(patient_msg)
    return user_msg, patient_msg
