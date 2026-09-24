# backend/tests/conftest.py
"""
Fixtures compartilhadas para toda a suíte de testes.

Dependências necessárias (adicionar ao pyproject.toml / requirements-dev.txt):
    pytest
    pytest-asyncio>=0.23
    httpx
    pytest-mock
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Configuração global do pytest-asyncio
# ---------------------------------------------------------------------------
pytest_plugins = ["pytest_asyncio"]

# Valor fixo usado pelo mock para server_default de created_at
_MOCK_CREATED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fábrica de pacientes virtuais mock
# ---------------------------------------------------------------------------

def make_patient(
    *,
    id: str | None = None,
    case_number: int = 1,
    eixo_a: str = "cardiovascular",
    eixo_b: str = "colaborativo",
    eixo_c: str = "baixo_letramento_vulneravel",
    complexidade: str = "media",
    nome: str = "Teste Silva",
    idade: int = 45,
    sexo: str = "M",
    queixa_principal: str = "Dor no peito",
    diagnostico_principal: str = "Angina Instável",
    is_active: bool = True,
    case_data: dict | None = None,
) -> MagicMock:
    """Retorna um objeto mock que imita VirtualPatient."""
    pid = uuid.UUID(id) if id else uuid.uuid4()
    p = MagicMock()
    p.id = pid
    p.case_number = case_number
    p.eixo_a = eixo_a
    p.eixo_b = eixo_b
    p.eixo_c = eixo_c
    p.complexidade = complexidade
    p.nome = nome
    p.idade = idade
    p.sexo = sexo
    p.queixa_principal = queixa_principal
    p.diagnostico_principal = diagnostico_principal
    p.is_active = is_active
    p.created_at = _MOCK_CREATED_AT
    p.case_data = case_data or {
        "identificacao": {"nome": nome, "idade": idade, "sexo": sexo},
        "queixa_principal_texto": queixa_principal,
        "historia_doenca_atual": "Paciente refere início há 3 dias.",
        "raw_sections": {
            "caracteristicas_agente": "Paciente colaborativo, fala pausado.",
        },
        "hipoteses_diagnosticas": [diagnostico_principal],
        "gerado_por_llm": False,
    }
    return p


# ---------------------------------------------------------------------------
# Sessão de DB mockada
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db_session():
    """
    AsyncMock que simula AsyncSession do SQLAlchemy.

    Rastreia objetos passados para add() e simula os defaults que o
    SQLAlchemy aplicaria em um flush/commit real: id (default=uuid.uuid4,
    client-side) e created_at/updated_at/is_active (server_default).
    Sem um banco real, esses valores continuam None até que esta fixture
    os preencha no flush() e no refresh(), permitindo que os schemas
    Pydantic (que exigem UUID/datetime, não Optional) validem os objetos
    corretamente em testes.
    """
    session = AsyncMock()
    _added: list = []

    def _add(obj) -> None:
        _added.append(obj)

    def _set_server_defaults(obj) -> None:
        if hasattr(obj, "id") and obj.id is None:
            obj.id = uuid.uuid4()
        if hasattr(obj, "created_at") and obj.created_at is None:
            obj.created_at = _MOCK_CREATED_AT
        if hasattr(obj, "updated_at") and obj.updated_at is None:
            obj.updated_at = _MOCK_CREATED_AT
        if hasattr(obj, "is_active") and obj.is_active is None:
            obj.is_active = True

    async def _flush() -> None:
        for obj in _added:
            _set_server_defaults(obj)

    async def _refresh(obj) -> None:
        _set_server_defaults(obj)

    session.add = MagicMock(side_effect=_add)
    session.flush = AsyncMock(side_effect=_flush)
    session.commit = AsyncMock()
    session.refresh = AsyncMock(side_effect=_refresh)
    return session


# ---------------------------------------------------------------------------
# Cliente HTTP com DB substituído
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def api_client(mock_db_session) -> AsyncGenerator[AsyncClient, None]:
    """
    AsyncClient apontando para a app FastAPI com get_db substituído pelo mock.
    """
    from app.db.database import get_db
    from app.main import app

    async def _override():
        yield mock_db_session

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Caso clínico JSON que imita resposta do GPT-4o
# ---------------------------------------------------------------------------

SAMPLE_CASE_JSON = {
    "nome": "João Cardoso",
    "idade": 55,
    "sexo": "M",
    "queixa_principal": "Dor no peito ao esforço",
    "diagnostico_principal": "Angina Estável",
    "historia_doenca_atual": (
        "O paciente relata dor precordial em aperto há 2 meses, "
        "desencadeada por esforços físicos moderados e aliviada pelo repouso."
    ),
    "identificacao": {
        "cor": "parda",
        "estado_civil": "casado",
        "profissao": "agricultor",
        "religiao": "católico",
        "residencia": "Teresina, PI",
        "naturalidade": "Piripiri, PI",
    },
    "interrogatorio_complementar": "Nega dispneia em repouso. Nega tosse.",
    "historia_fisiologica": "Desenvolvimento sem intercorrências.",
    "historia_patologica": {
        "doencas_previas": ["HAS", "DM2"],
        "cirurgias": [],
        "internacoes": [],
        "medicamentos_em_uso": ["Metformina 500mg 2x/dia", "Losartana 50mg 1x/dia"],
        "alergias": ["nega alergias"],
        "texto_livre": "HAS e DM2 diagnosticados há 10 anos.",
    },
    "historia_familiar": "Pai faleceu de IAM aos 60 anos.",
    "historia_social": {
        "tabagismo": "ex-tabagista, parou há 5 anos",
        "etilismo": "nega uso de álcool",
        "texto_livre": "Ensino fundamental incompleto. Mora em zona rural.",
    },
    "exame_fisico": "PA 145/90 mmHg. FC 78 bpm. Regular. Sem sopros.",
    "hipoteses_diagnosticas": ["Angina Estável", "Síndrome Coronariana Aguda"],
    "caracteristicas_agente": (
        "O paciente é um homem simples do campo, fala de forma pausada e direta. "
        "Demonstra alguma ansiedade ao relatar a dor, mas coopera plenamente. "
        "Minimiza a intensidade dos sintomas por receio de afastar-se do trabalho."
    ),
}
