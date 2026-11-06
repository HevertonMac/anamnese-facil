"""Lógica do chat: sessões, histórico, chamada ao LLM e registro de uso."""
from __future__ import annotations

import logging
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
from app.modules.chat.pricing import cost_usd
from app.modules.chat.prompt import build_system_prompt

log = logging.getLogger(__name__)


async def create_session(db: AsyncSession, user: User, patient_id: uuid.UUID) -> SimulationSession:
    patient = await db.get(VirtualPatient, patient_id)
    if patient is None or not patient.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paciente não encontrado")
    session = SimulationSession(patient_id=patient_id, student_id=user.id, status="active")
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

    patient = await db.get(VirtualPatient, session.patient_id)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paciente não encontrado")

    hist_stmt = (
        select(ConversationMessage)
        .where(ConversationMessage.session_id == session.id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(config.max_history())
    )
    history = list(reversed((await db.execute(hist_stmt)).scalars().all()))

    try:
        result = await get_provider().chat(
            system=build_system_prompt(patient.case_data),
            messages=_to_llm_messages(history, content),
            max_tokens=config.max_output_tokens(),
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
        content=result.text.strip(),
        created_at=now + timedelta(milliseconds=1),
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        model=result.model,
        provider=result.provider,
        cost_usd=cost_usd(result.provider, result.model, result.prompt_tokens, result.completion_tokens),
    )
    db.add(user_msg)
    db.add(patient_msg)
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(patient_msg)
    return user_msg, patient_msg


async def usage_summary(db: AsyncSession, days: int = 30) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    day = func.to_char(func.date_trunc("day", ConversationMessage.created_at), "YYYY-MM-DD")
    stmt = (
        select(
            day.label("day"),
            SimulationSession.student_id.label("user_id"),
            ConversationMessage.provider,
            ConversationMessage.model,
            func.count().label("messages"),
            func.coalesce(func.sum(ConversationMessage.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(ConversationMessage.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(ConversationMessage.cost_usd), 0).label("cost_usd"),
        )
        .join(SimulationSession, SimulationSession.id == ConversationMessage.session_id)
        .where(ConversationMessage.role == "assistant", ConversationMessage.created_at >= since)
        .group_by(day, SimulationSession.student_id, ConversationMessage.provider, ConversationMessage.model)
        .order_by(day.desc())
    )
    return [dict(r._mapping) for r in (await db.execute(stmt)).all()]
