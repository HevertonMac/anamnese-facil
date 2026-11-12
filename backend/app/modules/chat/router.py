"""Chat com paciente virtual: /chat/sessions, /chat/sessions/{id}/messages."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import User
from app.modules.auth.router import get_current_user
from app.modules.chat import config, service
from app.modules.chat.schemas import (
    MessageCreate,
    MessageOut,
    SendMessageResponse,
    SessionCreate,
    SessionDetail,
    SessionOut,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/config")
async def chat_config(user: User = Depends(get_current_user)):
    """Configuração para o frontend: modelos selecionáveis (admin)."""
    ids = config.allowed_models()
    default = config.model_name()
    if default and default not in ids:
        ids = [default, *ids]
    models = [{"id": m} for m in ids]
    return {
        "provider": config.provider_name(),
        "default_model": default,
        "models": models,
        "can_choose_model": user.role == "admin" and config.provider_name() == "openai",
    }


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def create_session(
    body: SessionCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    """Inicia uma sessão de anamnese com um paciente virtual."""
    return await service.create_session(db, user, body.patient_id, body.model)


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
    if user.role != "admin":  # o prompt do paciente tem o gabarito do caso
        detail.system_prompt = None
    return detail


@router.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_message(
    session_id: uuid.UUID,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Envia a fala do aluno e retorna a resposta do paciente."""
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
