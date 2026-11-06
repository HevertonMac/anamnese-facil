"""Testes do módulo de chat: prompt, preços, providers, serviço e API (LLM e DB mockados)."""
from __future__ import annotations

import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.modules.chat import pricing, service
from app.modules.chat.llm.anthropic_provider import AnthropicProvider
from app.modules.chat.llm.base import LLMError, LLMResult
from app.modules.chat.llm.openai_provider import OpenAIProvider
from app.modules.chat.prompt import build_system_prompt
from tests.conftest import SAMPLE_CASE_JSON, make_patient


def _user(role: str = "student") -> MagicMock:
    u = MagicMock()
    u.id = uuid.uuid4()
    u.role = role
    u.is_active = True
    return u


def _session(user, status: str = "active") -> MagicMock:
    s = MagicMock()
    s.id = uuid.uuid4()
    s.patient_id = uuid.uuid4()
    s.student_id = user.id
    s.status = status
    return s


class FakeProvider:
    name = "openai"
    model = "gpt-4o-mini"

    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[dict] = []

    async def chat(self, system, messages, max_tokens, temperature=0.7):
        self.calls.append({"system": system, "messages": messages, "max_tokens": max_tokens})
        if self.error:
            raise self.error
        return LLMResult("Dói aqui, doutor.", 1000, 20, "gpt-4o-mini", "openai")


def _db_with_counts(mock_db_session, patient, count: int = 0, history=None):
    mock_db_session.get = AsyncMock(return_value=patient)
    result = MagicMock()
    result.scalar.return_value = count
    result.scalars.return_value.all.return_value = history or []
    mock_db_session.execute = AsyncMock(return_value=result)


# ── prompt ────────────────────────────────────────────────────────────────────

def test_prompt_contem_perfil_historia_e_regras():
    case = {**SAMPLE_CASE_JSON, "agente_ia": {"perfil": "Homem simples do campo", "vocabulario": "coloquial"}}
    prompt = build_system_prompt(case)
    assert "PACIENTE VIRTUAL" in prompt
    assert "Homem simples do campo" in prompt
    assert "dor precordial" in prompt
    assert "Pai faleceu de IAM" in prompt
    assert "só revele se o estudante examinar" in prompt


def test_prompt_usa_caracteristicas_agente_quando_sem_agente_ia():
    prompt = build_system_prompt(SAMPLE_CASE_JSON)
    assert "fala de forma pausada" in prompt


# ── preços ────────────────────────────────────────────────────────────────────

def test_custo_gpt4o_mini():
    # 1M entrada * 0.15 + 1M saída * 0.60
    assert pricing.cost_usd("openai", "gpt-4o-mini", 1_000_000, 1_000_000) == Decimal("0.75")


def test_custo_modelo_datado_casa_por_prefixo_mais_longo():
    assert pricing.cost_usd("openai", "gpt-4o-mini-2024-07-18", 1_000_000, 0) == Decimal("0.15")


def test_custo_modelo_desconhecido_e_zero():
    assert pricing.cost_usd("anthropic", "modelo-x", 10, 10) == Decimal(0)


def test_custo_com_precos_via_env(monkeypatch):
    monkeypatch.setenv("CHAT_PRICES_JSON", json.dumps({"anthropic:modelo-x": [2, 10]}))
    assert pricing.cost_usd("anthropic", "modelo-x", 1_000_000, 100_000) == Decimal("3")


# ── providers (parsing de usage) ──────────────────────────────────────────────

def _patch_httpx(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(
        "httpx.AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **{k: v for k, v in kw.items()})
    )


async def test_openai_provider_le_usage(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["messages"][0]["role"] == "system"
        assert body["max_tokens"] == 50
        return httpx.Response(200, json={
            "model": "gpt-4o-mini-2024-07-18",
            "choices": [{"message": {"content": "Oi"}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3},
        })

    _patch_httpx(monkeypatch, handler)
    r = await OpenAIProvider("gpt-4o-mini").chat("sys", [{"role": "user", "content": "x"}], 50)
    assert (r.text, r.prompt_tokens, r.completion_tokens, r.provider) == ("Oi", 12, 3, "openai")


async def test_anthropic_provider_le_usage(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["system"] == "sys" and request.headers["x-api-key"] == "sk-ant-test"
        return httpx.Response(200, json={
            "model": "m", "content": [{"type": "text", "text": "Olá"}],
            "usage": {"input_tokens": 20, "output_tokens": 5},
        })

    _patch_httpx(monkeypatch, handler)
    r = await AnthropicProvider("m").chat("sys", [{"role": "user", "content": "x"}], 50)
    assert (r.text, r.prompt_tokens, r.completion_tokens, r.provider) == ("Olá", 20, 5, "anthropic")


async def test_provider_http_error_vira_llmerror(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    _patch_httpx(monkeypatch, lambda req: httpx.Response(500, json={}))
    with pytest.raises(LLMError):
        await OpenAIProvider("m").chat("s", [], 10)


async def test_provider_sem_chave_levanta_not_configured(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from app.modules.chat.llm.base import LLMNotConfigured
    with pytest.raises(LLMNotConfigured):
        await OpenAIProvider("m").chat("s", [], 10)


# ── serviço ───────────────────────────────────────────────────────────────────

async def test_send_message_registra_uso_e_custo(mock_db_session, monkeypatch):
    user, fake = _user(), FakeProvider()
    monkeypatch.setattr(service, "get_provider", lambda: fake)
    _db_with_counts(mock_db_session, make_patient())

    user_msg, patient_msg = await service.send_message(mock_db_session, _session(user), user, " Qual sua queixa? ")

    assert user_msg.content == "Qual sua queixa?" and user_msg.role == "user"
    assert patient_msg.role == "assistant" and patient_msg.prompt_tokens == 1000
    assert patient_msg.cost_usd == Decimal("0.000162")  # 1000*0.15/1e6 + 20*0.60/1e6
    assert patient_msg.created_at > user_msg.created_at
    assert fake.calls[0]["messages"][-1] == {"role": "user", "content": "Qual sua queixa?"}
    mock_db_session.commit.assert_awaited()


async def test_send_message_descarta_assistant_inicial_do_historico(mock_db_session, monkeypatch):
    user, fake = _user(), FakeProvider()
    monkeypatch.setattr(service, "get_provider", lambda: fake)
    old = MagicMock(role="assistant", content="resposta antiga")
    _db_with_counts(mock_db_session, make_patient(), history=[old])

    await service.send_message(mock_db_session, _session(user), user, "oi")
    assert fake.calls[0]["messages"] == [{"role": "user", "content": "oi"}]


async def test_send_message_sessao_encerrada(mock_db_session):
    from fastapi import HTTPException
    user = _user()
    with pytest.raises(HTTPException) as e:
        await service.send_message(mock_db_session, _session(user, "ended"), user, "oi")
    assert e.value.status_code == 409


async def test_send_message_limite_por_sessao(mock_db_session, monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setenv("CHAT_MAX_MESSAGES_PER_SESSION", "4")
    user = _user()
    _db_with_counts(mock_db_session, make_patient(), count=4)
    with pytest.raises(HTTPException) as e:
        await service.send_message(mock_db_session, _session(user), user, "oi")
    assert e.value.status_code == 429


async def test_send_message_mensagem_longa_demais(mock_db_session, monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setenv("CHAT_MAX_MESSAGE_CHARS", "10")
    user = _user()
    with pytest.raises(HTTPException) as e:
        await service.send_message(mock_db_session, _session(user), user, "x" * 11)
    assert e.value.status_code == 422


async def test_send_message_llm_falha_vira_502_sem_persistir(mock_db_session, monkeypatch):
    from fastapi import HTTPException
    user = _user()
    monkeypatch.setattr(service, "get_provider", lambda: FakeProvider(error=LLMError("boom")))
    _db_with_counts(mock_db_session, make_patient())
    with pytest.raises(HTTPException) as e:
        await service.send_message(mock_db_session, _session(user), user, "oi")
    assert e.value.status_code == 502
    mock_db_session.commit.assert_not_awaited()


# ── API ───────────────────────────────────────────────────────────────────────

@pytest.fixture
def as_user(api_client):
    from app.main import app
    from app.modules.auth.router import get_current_user

    def _set(user):
        app.dependency_overrides[get_current_user] = lambda: user

    return _set


async def test_api_exige_login(api_client):
    r = await api_client.post("/api/v1/chat/sessions", json={"patient_id": str(uuid.uuid4())})
    assert r.status_code in (401, 403)


async def test_api_criar_sessao_paciente_inexistente(api_client, mock_db_session, as_user):
    as_user(_user())
    mock_db_session.get = AsyncMock(return_value=None)
    r = await api_client.post("/api/v1/chat/sessions", json={"patient_id": str(uuid.uuid4())})
    assert r.status_code == 404


async def test_api_fluxo_mensagem(api_client, mock_db_session, as_user, monkeypatch):
    user = _user()
    as_user(user)
    sess = _session(user)
    monkeypatch.setattr(service, "get_session", AsyncMock(return_value=sess))
    monkeypatch.setattr(service, "get_provider", lambda: FakeProvider())
    _db_with_counts(mock_db_session, make_patient())

    r = await api_client.post(f"/api/v1/chat/sessions/{sess.id}/messages", json={"content": "Bom dia"})
    assert r.status_code == 200
    body = r.json()
    assert body["patient_message"]["content"] == "Dói aqui, doutor."
    assert body["patient_message"]["prompt_tokens"] == 1000
    assert body["user_message"]["role"] == "user"


async def test_api_sessao_alheia_403(api_client, mock_db_session, as_user):
    as_user(_user())
    other = _session(_user())
    result = MagicMock()
    result.scalar_one_or_none.return_value = other
    mock_db_session.execute = AsyncMock(return_value=result)
    r = await api_client.post(f"/api/v1/chat/sessions/{other.id}/messages", json={"content": "oi"})
    assert r.status_code == 403


async def test_api_usage_so_admin(api_client, as_user):
    as_user(_user("student"))
    r = await api_client.get("/api/v1/chat/usage")
    assert r.status_code == 403


# ── humanização / limpeza da resposta ─────────────────────────────────────────

def test_prompt_pede_fala_humana():
    prompt = build_system_prompt(SAMPLE_CASE_JSON)
    assert "NÃO é um assistente" in prompt
    assert "Nada de listas" in prompt


@pytest.mark.parametrize("raw,expected", [
    ("Paciente: Tô com dor, doutor.", "Tô com dor, doutor."),
    ('"Bom dia, doutor."', "Bom dia, doutor."),
    ("É **forte** mesmo.", "É forte mesmo."),
    ("- dói aqui\n- e aqui", "dói aqui\ne aqui"),
])
def test_clean_reply(raw, expected):
    assert service.clean_reply(raw) == expected


async def test_send_message_grava_latencia_e_temperatura(mock_db_session, monkeypatch):
    monkeypatch.setenv("CHAT_TEMPERATURE", "0.95")
    user = _user()
    seen = {}

    class P(FakeProvider):
        async def chat(self, system, messages, max_tokens, temperature=0.7):
            seen["t"] = temperature
            return await super().chat(system, messages, max_tokens, temperature)

    monkeypatch.setattr(service, "get_provider", lambda: P())
    _db_with_counts(mock_db_session, make_patient())
    _, patient_msg = await service.send_message(mock_db_session, _session(user), user, "oi")
    assert seen["t"] == 0.95
    assert isinstance(patient_msg.latency_ms, int) and patient_msg.latency_ms >= 0


# ── resumo por sessão / CSV ───────────────────────────────────────────────────

def test_sessions_usage_csv():
    rows = [{
        "session_id": "s1", "user_email": "a@b.c", "case_number": 3, "status": "ended",
        "started_at": "2026-11-06", "ended_at": None, "turns": 4, "provider": "openai",
        "model": "gpt-4o-mini", "prompt_tokens": 100, "completion_tokens": 20,
        "cost_usd": Decimal("0.0003"), "avg_latency_ms": 800,
    }]
    lines = service.sessions_usage_csv(rows).strip().splitlines()
    assert lines[0].startswith("session_id,user_email,case_number")
    assert lines[1].startswith("s1,a@b.c,3,ended,2026-11-06,,4,openai,gpt-4o-mini,100,20,0.0003,800")


async def test_api_usage_sessions_so_admin(api_client, as_user):
    as_user(_user("student"))
    assert (await api_client.get("/api/v1/chat/usage/sessions")).status_code == 403
    assert (await api_client.get("/api/v1/chat/usage/sessions.csv")).status_code == 403


async def test_api_usage_sessions_csv_admin(api_client, as_user, monkeypatch):
    as_user(_user("admin"))
    monkeypatch.setattr(service, "sessions_usage", AsyncMock(return_value=[]))
    r = await api_client.get("/api/v1/chat/usage/sessions.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.text.startswith("session_id,")
