"""Análise de custos do chat (visão de desenvolvimento): agregações, comparação de modelos e export."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ConversationMessage, SimulationSession, User, VirtualPatient

_M = ConversationMessage


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _metrics() -> list:
    """Colunas agregadas comuns (sobre as respostas do paciente = chamadas ao LLM)."""
    return [
        func.count(distinct(_M.session_id)).label("sessions"),
        func.count().label("turns"),
        func.coalesce(func.sum(_M.prompt_tokens), 0).label("prompt_tokens"),
        func.coalesce(func.sum(_M.completion_tokens), 0).label("completion_tokens"),
        func.coalesce(func.sum(_M.cost_usd), 0).label("cost_usd"),
        func.avg(_M.latency_ms).label("avg_latency_ms"),
        func.percentile_cont(0.95).within_group(_M.latency_ms).label("p95_latency_ms"),
    ]


def _finish(row: dict) -> dict:
    """Converte tipos e acrescenta custo por turno/sessão e tokens médios por turno."""
    cost = Decimal(row["cost_usd"] or 0)
    turns, sessions = int(row["turns"]), int(row["sessions"])
    row["cost_usd"] = cost
    row["avg_latency_ms"] = int(row["avg_latency_ms"]) if row["avg_latency_ms"] is not None else None
    row["p95_latency_ms"] = int(row["p95_latency_ms"]) if row["p95_latency_ms"] is not None else None
    row["cost_per_turn"] = (cost / turns) if turns else Decimal(0)
    row["cost_per_session"] = (cost / sessions) if sessions else Decimal(0)
    row["avg_prompt_tokens_per_turn"] = round(int(row["prompt_tokens"]) / turns) if turns else 0
    row["avg_completion_tokens_per_turn"] = round(int(row["completion_tokens"]) / turns) if turns else 0
    return row


async def _grouped(db: AsyncSession, days: int, label: str | None = None, expr: Any = None) -> list[dict]:
    stmt = (
        select(*([expr.label(label)] if expr is not None else []), *_metrics())
        .select_from(_M)
        .join(SimulationSession, SimulationSession.id == _M.session_id)
        .join(User, User.id == SimulationSession.student_id)
        .join(VirtualPatient, VirtualPatient.id == SimulationSession.patient_id)
        .where(_M.role == "assistant", _M.created_at >= _since(days))
    )
    if expr is not None:
        stmt = stmt.group_by(expr).order_by(func.sum(_M.cost_usd).desc().nulls_last())
    return [_finish(dict(r._mapping)) for r in (await db.execute(stmt)).all()]


async def summary(db: AsyncSession, days: int = 30) -> dict:
    totals = await _grouped(db, days)
    day = func.to_char(func.date_trunc("day", _M.created_at), "YYYY-MM-DD")
    by_day = await _grouped(db, days, "day", day)
    return {
        "days": days,
        "totals": totals[0] if totals else _finish({
            "sessions": 0, "turns": 0, "prompt_tokens": 0, "completion_tokens": 0,
            "cost_usd": 0, "avg_latency_ms": None, "p95_latency_ms": None,
        }),
        "by_day": sorted(by_day, key=lambda r: r["day"]),
        "by_model": await _grouped(db, days, "model", func.coalesce(_M.model, "?")),
        "by_case": await _grouped(db, days, "case_number", VirtualPatient.case_number),
        "by_user": await _grouped(db, days, "user_email", User.email),
    }


async def models_comparison(db: AsyncSession, days: int = 30) -> list[dict]:
    return await _grouped(db, days, "model", func.coalesce(_M.model, "?"))


async def export_sessions(db: AsyncSession, days: int = 30) -> list[dict]:
    """Sessões com contexto (modelo, temperatura, prompt) e todas as mensagens."""
    stmt = (
        select(SimulationSession, User.email, VirtualPatient.case_number)
        .join(User, User.id == SimulationSession.student_id)
        .join(VirtualPatient, VirtualPatient.id == SimulationSession.patient_id)
        .where(SimulationSession.started_at >= _since(days))
        .options(selectinload(SimulationSession.messages))
        .order_by(SimulationSession.started_at.desc())
    )
    out = []
    for s, email, case_number in (await db.execute(stmt)).all():
        msgs = sorted(s.messages, key=lambda m: m.created_at)
        out.append({
            "session_id": s.id, "user_email": email, "case_number": case_number, "status": s.status,
            "started_at": s.started_at, "ended_at": s.ended_at, "provider": s.provider, "model": s.model,
            "temperature": s.temperature, "system_prompt_tokens": s.system_prompt_tokens,
            "system_prompt": s.system_prompt,
            "total_cost_usd": sum((m.cost_usd or Decimal(0) for m in msgs), Decimal(0)),
            "messages": [{
                "role": m.role, "content": m.content, "created_at": m.created_at,
                "prompt_tokens": m.prompt_tokens, "completion_tokens": m.completion_tokens,
                "model": m.model, "cost_usd": m.cost_usd, "latency_ms": m.latency_ms,
            } for m in msgs],
        })
    return out


def to_json(data: Any) -> str:
    return json.dumps(data, default=str, ensure_ascii=False, indent=2)
