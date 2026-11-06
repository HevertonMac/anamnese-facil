"""Chat com paciente virtual: /chat/sessions, /chat/sessions/{id}/messages, /chat/usage."""
from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import User
from app.modules.auth.router import get_current_user, require_admin
from app.modules.chat import service
from app.modules.chat.schemas import (
    MessageCreate,
    MessageOut,
    SendMessageResponse,
    SessionCreate,
    SessionDetail,
    SessionOut,
    SessionUsageRow,
    UsageRow,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def create_session(
    body: SessionCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    """Inicia uma sessão de anamnese com um paciente virtual."""
    return await service.create_session(db, user, body.patient_id)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await service.list_sessions(db, user)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    session = await service.get_session(db, session_id, user, with_messages=True)
    messages = sorted(session.messages, key=lambda m: m.created_at)
    detail = SessionDetail.model_validate(session)
    detail.messages = [MessageOut.model_validate(m) for m in messages]
    detail.total_tokens = sum((m.prompt_tokens or 0) + (m.completion_tokens or 0) for m in messages)
    detail.total_cost_usd = sum((m.cost_usd or Decimal(0) for m in messages), Decimal(0))
    return detail


@router.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_message(
    session_id: uuid.UUID,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Envia a fala do aluno e retorna a resposta do paciente (com tokens e custo)."""
    session = await service.get_session(db, session_id, user)
    user_msg, patient_msg = await service.send_message(db, session, user, body.content)
    return SendMessageResponse(
        user_message=MessageOut.model_validate(user_msg),
        patient_message=MessageOut.model_validate(patient_msg),
    )


@router.post("/sessions/{session_id}/end", response_model=SessionOut)
async def end_session(
    session_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    session = await service.get_session(db, session_id, user)
    return await service.end_session(db, session)


@router.get("/usage", response_model=list[UsageRow])
async def usage(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Uso de tokens e custo agregados por dia/usuário/modelo (admin)."""
    return await service.usage_summary(db, days)


@router.get("/usage/sessions", response_model=list[SessionUsageRow])
async def usage_sessions(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Uma linha por sessão (aluno, caso, turnos, tokens, custo, latência) para análise de custos (admin)."""
    return await service.sessions_usage(db, days)


@router.get("/usage/sessions.csv")
async def usage_sessions_csv(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Mesmo conteúdo de /usage/sessions em CSV."""
    csv_text = service.sessions_usage_csv(await service.sessions_usage(db, days))
    return Response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="chat_usage_sessions.csv"'},
    )
