"""Pydantic schemas do chat."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    patient_id: uuid.UUID
    model: Optional[str] = None  # só admin; deve estar em CHAT_ALLOWED_MODELS


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionOut(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    student_id: uuid.UUID
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None

    model_config = {"from_attributes": True}


class SessionDetail(SessionOut):
    system_prompt: Optional[str] = None  # preenchido só para admin
    messages: list[MessageOut] = []


class SendMessageResponse(BaseModel):
    user_message: MessageOut
    patient_message: MessageOut
