# backend/tests/test_api_kb.py
"""
Testes de integração para o módulo knowledge_base (GET/POST /api/v1/kb/*).

Usa AsyncClient do httpx com get_db substituído por uma sessão mockada,
sem necessidade de banco de dados real.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from conftest import make_patient

pytestmark = pytest.mark.asyncio


# ===========================================================================
# GET /api/v1/kb/patients
# ===========================================================================

class TestListPatients:
    async def test_returns_list_of_patients(self, api_client, mock_db_session):
        p1 = make_patient(case_number=1, eixo_a="cardiovascular")
        p2 = make_patient(case_number=2, eixo_a="neurologico")

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [p1, p2]
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        resp = await api_client.get("/api/v1/kb/patients")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["case_number"] == 1
        assert data[1]["case_number"] == 2

    async def test_returns_empty_list_when_no_patients(self, api_client, mock_db_session):
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        resp = await api_client.get("/api/v1/kb/patients")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_response_fields(self, api_client, mock_db_session):
        p = make_patient()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [p]
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        resp = await api_client.get("/api/v1/kb/patients")
        patient = resp.json()[0]

        required_fields = {"id", "case_number", "eixo_a", "eixo_b", "eixo_c",
                           "complexidade", "nome", "idade", "sexo",
                           "queixa_principal", "diagnostico_principal",
                           "is_active", "created_at"}
        assert required_fields.issubset(patient.keys())

    async def test_response_does_not_include_case_data(self, api_client, mock_db_session):
        """VirtualPatientResponse (lista) não deve expor case_data completo."""
        p = make_patient()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [p]
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        resp = await api_client.get("/api/v1/kb/patients")
        patient = resp.json()[0]
        assert "case_data" not in patient

    async def test_filter_by_eixo_a_passes_to_query(self, api_client, mock_db_session):
        """Verificar que o parâmetro eixo_a é aceito sem erro 422."""
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        resp = await api_client.get("/api/v1/kb/patients?eixo_a=cardiovascular")
        assert resp.status_code == 200

    async def test_filter_by_complexidade_passes_to_query(self, api_client, mock_db_session):
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        resp = await api_client.get("/api/v1/kb/patients?complexidade=alta")
        assert resp.status_code == 200

    async def test_active_only_true_by_default(self, api_client, mock_db_session):
        """active_only=true é o padrão — o endpoint deve aceitar sem parâmetro."""
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        resp = await api_client.get("/api/v1/kb/patients")
        assert resp.status_code == 200


# ===========================================================================
# GET /api/v1/kb/patients/{patient_id}
# ===========================================================================

class TestGetPatient:
    async def test_returns_patient_with_case_data(self, api_client, mock_db_session):
        p = make_patient()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = p
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        resp = await api_client.get(f"/api/v1/kb/patients/{p.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(p.id)
        assert "case_data" in data

    async def test_case_data_contains_raw_sections(self, api_client, mock_db_session):
        p = make_patient()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = p
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        resp = await api_client.get(f"/api/v1/kb/patients/{p.id}")
        case_data = resp.json()["case_data"]
        assert "raw_sections" in case_data
        assert "caracteristicas_agente" in case_data["raw_sections"]

    async def test_returns_404_for_unknown_patient(self, api_client, mock_db_session):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        unknown_id = uuid.uuid4()
        resp = await api_client.get(f"/api/v1/kb/patients/{unknown_id}")
        assert resp.status_code == 404

    async def test_invalid_uuid_returns_422(self, api_client, mock_db_session):
        resp = await api_client.get("/api/v1/kb/patients/nao-e-um-uuid")
        assert resp.status_code == 422


# ===========================================================================
# POST /api/v1/kb/patients
# ===========================================================================

class TestCreatePatient:
    VALID_PAYLOAD = {
        "case_number": 99,
        "eixo_a": "neurologico",
        "eixo_b": "ansioso",
        "eixo_c": "medio_letramento_media",
        "complexidade": "alta",
        "nome": "Ana Lima",
        "idade": 32,
        "sexo": "F",
        "queixa_principal": "Cefaleia intensa",
        "diagnostico_principal": "Enxaqueca",
        "case_data": {
            "identificacao": {"nome": "Ana Lima", "idade": 32, "sexo": "F"},
            "queixa_principal_texto": "Cefaleia intensa",
            "historia_doenca_atual": "Cefaleias recorrentes há 5 anos.",
            "hipoteses_diagnosticas": ["Enxaqueca"],
            "raw_sections": {"caracteristicas_agente": "Paciente ansiosa."},
        },
    }

    async def test_creates_patient_successfully(self, api_client, mock_db_session):
        # Simula que o case_number ainda não existe
        check_mock = MagicMock()
        check_mock.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=check_mock)
        # Não patchamos VirtualPatient: o select(VirtualPatient) do SQLAlchemy
        # precisa da classe real; created_at é definido pelo side_effect do flush
        # no fixture mock_db_session (server_default simulado).

        resp = await api_client.post("/api/v1/kb/patients", json=self.VALID_PAYLOAD)
        assert resp.status_code == 201

    async def test_duplicate_case_number_returns_409(self, api_client, mock_db_session):
        existing = make_patient(case_number=99)
        check_mock = MagicMock()
        check_mock.scalar_one_or_none.return_value = existing
        mock_db_session.execute = AsyncMock(return_value=check_mock)

        resp = await api_client.post("/api/v1/kb/patients", json=self.VALID_PAYLOAD)
        assert resp.status_code == 409

    async def test_missing_required_field_returns_422(self, api_client, mock_db_session):
        payload = dict(self.VALID_PAYLOAD)
        del payload["nome"]
        resp = await api_client.post("/api/v1/kb/patients", json=payload)
        assert resp.status_code == 422


# ===========================================================================
# GET /api/v1/kb/stats
# ===========================================================================

class TestStats:
    async def test_returns_expected_structure(self, api_client, mock_db_session):
        # scalar retorna contagens
        mock_db_session.scalar = AsyncMock(side_effect=[10, 50, 48])

        # execute retorna distribuição por área
        area_rows = [
            MagicMock(eixo_a="cardiovascular", count=3),
            MagicMock(eixo_a="neurologico", count=2),
        ]
        area_result = MagicMock()
        area_result.__iter__ = MagicMock(return_value=iter(area_rows))
        mock_db_session.execute = AsyncMock(return_value=area_result)

        resp = await api_client.get("/api/v1/kb/stats")
        assert resp.status_code == 200
        data = resp.json()

        assert "total_patients" in data
        assert "total_chunks" in data
        assert "embedded_chunks" in data
        assert "embedding_coverage" in data
        assert "by_clinical_area" in data

    async def test_by_clinical_area_has_enum_keys(self, api_client, mock_db_session):
        """As chaves de by_clinical_area devem ser os valores do enum EixoA."""
        from app.db.models import EixoA

        mock_db_session.scalar = AsyncMock(side_effect=[5, 20, 20])
        area_rows = [MagicMock(eixo_a=v.value, count=1) for v in EixoA]
        area_result = MagicMock()
        area_result.__iter__ = MagicMock(return_value=iter(area_rows))
        mock_db_session.execute = AsyncMock(return_value=area_result)

        resp = await api_client.get("/api/v1/kb/stats")
        data = resp.json()
        for key in data["by_clinical_area"]:
            assert key in {v.value for v in EixoA}, (
                f"Chave inesperada em by_clinical_area: {key!r}"
            )


# ===========================================================================
# POST /api/v1/kb/search
# ===========================================================================

class TestSearch:
    async def test_search_returns_list(self, api_client, mock_db_session):
        row = MagicMock(
            patient_id=uuid.uuid4(),
            patient_name="João",
            section="queixa_principal",
            content="Dor no peito",
            similarity=0.85,
        )
        result_mock = MagicMock()
        result_mock.__iter__ = MagicMock(return_value=iter([row]))
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        with patch("app.core.embeddings.get_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.0] * 1536  # zero vector → keyword search
            resp = await api_client.post(
                "/api/v1/kb/search",
                json={"query": "dor no peito", "top_k": 5},
            )

        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_search_with_patient_filter(self, api_client, mock_db_session):
        result_mock = MagicMock()
        result_mock.__iter__ = MagicMock(return_value=iter([]))
        mock_db_session.execute = AsyncMock(return_value=result_mock)

        patient_id = str(uuid.uuid4())
        with patch("app.core.embeddings.get_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.0] * 1536
            resp = await api_client.post(
                "/api/v1/kb/search",
                json={"query": "cefaleia", "patient_id": patient_id, "top_k": 3},
            )
        assert resp.status_code == 200

    async def test_search_top_k_validation(self, api_client, mock_db_session):
        resp = await api_client.post(
            "/api/v1/kb/search",
            json={"query": "teste", "top_k": 0},   # ge=1 → inválido
        )
        assert resp.status_code == 422

    async def test_search_top_k_max_validation(self, api_client, mock_db_session):
        resp = await api_client.post(
            "/api/v1/kb/search",
            json={"query": "teste", "top_k": 21},  # le=20 → inválido
        )
        assert resp.status_code == 422


# ===========================================================================
# GET /health
# ===========================================================================

class TestHealth:
    async def test_health_ok(self, api_client):
        resp = await api_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "anamnese-facil-api"
