"""Pydantic schemas do chat."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    patient_id: uuid.UUID


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    cost_usd: Optional[Decimal] = None
    latency_ms: Optional[int] = None

    model_config = {"from_attributes": True}


class SessionOut(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    student_id: uuid.UUID
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SessionDetail(SessionOut):
    messages: list[MessageOut] = []
    total_tokens: int = 0
    total_cost_usd: Decimal = Decimal(0)


class SendMessageResponse(BaseModel):
    user_message: MessageOut
    patient_message: MessageOut


class UsageRow(BaseModel):
    day: str
    user_id: Optional[uuid.UUID] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    messages: int
    prompt_tokens: int
    completion_tokens: int
    cost_usd: Decimal


class SessionUsageRow(BaseModel):
    session_id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    patient_id: uuid.UUID
    case_number: int
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    turns: int
    provider: Optional[str] = None
    model: Optional[str] = None
    prompt_tokens: int
    completion_tokens: int
    cost_usd: Decimal
    avg_latency_ms: Optional[int] = None
