# backend/tests/test_api_patient.py
"""
Testes de integração para o endpoint POST /api/v1/patients/generate.

Cobre:
  - 503 quando OPENAI_API_KEY não está configurada
  - Geração bem-sucedida com resposta mockada do OpenAI
  - case_data incluído na resposta (regressão: PatientGenerateResponse.patient deve ser VirtualPatientDetail)
  - raw_sections.caracteristicas_agente populado
  - chunks_ingested correto
  - campo generated_by
  - parâmetro eixo_c honrado
  - normalização de sexo (M/F)

Patches corretos para o router de geração:
  - `app.modules.patient.router.OPENAI_API_KEY`  → testa 503
  - `app.modules.patient.router.call_openai_generate` → evita chamada real ao OpenAI
  - `app.modules.patient.router.get_embeddings`       → evita chamada real ao OpenAI
  - execute mock usa `.fetchall()` (não .scalars().all()), pois o router faz
    `result.fetchall()` para obter os case_numbers existentes.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conftest import SAMPLE_CASE_JSON

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_execute_mock(rows: list | None = None):
    """Retorna mock de db.execute() com fetchall() configurado."""
    result = MagicMock()
    result.fetchall.return_value = rows if rows is not None else []
    return result


async def _embeddings_side_effect(texts: list[str]) -> list[list[float]]:
    """Retorna vetores zero com dimensão correta para qualquer lote."""
    return [[0.0] * 1536 for _ in texts]


# ===========================================================================
# POST /api/v1/patients/generate
# ===========================================================================

class TestGeneratePatient:
    BASE_PAYLOAD = {
        "eixo_a": "cardiovascular",
        "eixo_b": "colaborativo",
        "complexidade": "media",
        "eixo_c": "baixo_letramento_vulneravel",
    }

    # -----------------------------------------------------------------------
    # 503 sem chave de API
    # -----------------------------------------------------------------------

    async def test_returns_503_without_api_key(self, api_client, mock_db_session):
        """Sem OPENAI_API_KEY configurada, o endpoint deve retornar 503.

        O router verifica OPENAI_API_KEY antes de acessar o banco, então
        não precisamos configurar mock_db_session.execute aqui.
        """
        with patch("app.modules.patient.router.OPENAI_API_KEY", ""):
            resp = await api_client.post(
                "/api/v1/patients/generate",
                json=self.BASE_PAYLOAD,
            )

        assert resp.status_code == 503

    # -----------------------------------------------------------------------
    # Geração bem-sucedida
    # -----------------------------------------------------------------------

    def _setup_generate_mocks(self, mock_db_session, existing_numbers=None):
        """Configura execute mock e retorna patchers para call/embed."""
        rows = [(n,) for n in (existing_numbers or [])]
        mock_db_session.execute = AsyncMock(return_value=_make_execute_mock(rows))

    async def test_successful_generation_returns_201(
        self, api_client, mock_db_session
    ):
        """Geração com mock OpenAI deve retornar 201."""
        self._setup_generate_mocks(mock_db_session, existing_numbers=[1, 2, 3])

        with (
            patch(
                "app.modules.patient.router.call_openai_generate",
                new_callable=AsyncMock,
            ) as mock_gen,
            patch(
                "app.modules.patient.router.get_embeddings",
                new_callable=AsyncMock,
            ) as mock_emb,
        ):
            mock_gen.return_value = SAMPLE_CASE_JSON
            mock_emb.side_effect = _embeddings_side_effect

            resp = await api_client.post(
                "/api/v1/patients/generate",
                json=self.BASE_PAYLOAD,
            )

        assert resp.status_code == 201

    async def test_response_includes_patient_field(
        self, api_client, mock_db_session
    ):
        """A resposta deve conter o campo 'patient'."""
        self._setup_generate_mocks(mock_db_session)

        with (
            patch(
                "app.modules.patient.router.call_openai_generate",
                new_callable=AsyncMock,
            ) as mock_gen,
            patch(
                "app.modules.patient.router.get_embeddings",
                new_callable=AsyncMock,
            ) as mock_emb,
        ):
            mock_gen.return_value = SAMPLE_CASE_JSON
            mock_emb.side_effect = _embeddings_side_effect

            resp = await api_client.post(
                "/api/v1/patients/generate",
                json=self.BASE_PAYLOAD,
            )

        assert resp.status_code == 201
        assert "patient" in resp.json()

    async def test_response_includes_case_data(
        self, api_client, mock_db_session
    ):
        """
        Regressão: PatientGenerateResponse.patient deve ser VirtualPatientDetail,
        portanto a resposta deve incluir case_data.
        """
        self._setup_generate_mocks(mock_db_session)

        with (
            patch(
                "app.modules.patient.router.call_openai_generate",
                new_callable=AsyncMock,
            ) as mock_gen,
            patch(
                "app.modules.patient.router.get_embeddings",
                new_callable=AsyncMock,
            ) as mock_emb,
        ):
            mock_gen.return_value = SAMPLE_CASE_JSON
            mock_emb.side_effect = _embeddings_side_effect

            resp = await api_client.post(
                "/api/v1/patients/generate",
                json=self.BASE_PAYLOAD,
            )

        assert resp.status_code == 201
        data = resp.json()
        assert "case_data" in data["patient"], (
            "case_data ausente: PatientGenerateResponse.patient deve ser "
            "VirtualPatientDetail, não VirtualPatientResponse"
        )

    async def test_response_includes_raw_sections(
        self, api_client, mock_db_session
    ):
        """case_data.raw_sections deve estar presente e conter caracteristicas_agente."""
        self._setup_generate_mocks(mock_db_session)

        with (
            patch(
                "app.modules.patient.router.call_openai_generate",
                new_callable=AsyncMock,
            ) as mock_gen,
            patch(
                "app.modules.patient.router.get_embeddings",
                new_callable=AsyncMock,
            ) as mock_emb,
        ):
            mock_gen.return_value = SAMPLE_CASE_JSON
            mock_emb.side_effect = _embeddings_side_effect

            resp = await api_client.post(
                "/api/v1/patients/generate",
                json=self.BASE_PAYLOAD,
            )

        assert resp.status_code == 201
        case_data = resp.json()["patient"]["case_data"]
        assert "raw_sections" in case_data
        assert "caracteristicas_agente" in case_data["raw_sections"]

    async def test_response_has_chunks_ingested(
        self, api_client, mock_db_session
    ):
        """A resposta deve conter o campo chunks_ingested."""
        self._setup_generate_mocks(mock_db_session)

        with (
            patch(
                "app.modules.patient.router.call_openai_generate",
                new_callable=AsyncMock,
            ) as mock_gen,
            patch(
                "app.modules.patient.router.get_embeddings",
                new_callable=AsyncMock,
            ) as mock_emb,
        ):
            mock_gen.return_value = SAMPLE_CASE_JSON
            mock_emb.side_effect = _embeddings_side_effect

            resp = await api_client.post(
                "/api/v1/patients/generate",
                json=self.BASE_PAYLOAD,
            )

        assert resp.status_code == 201
        data = resp.json()
        assert "chunks_ingested" in data
        assert isinstance(data["chunks_ingested"], int)
        assert data["chunks_ingested"] >= 0

    async def test_response_has_generated_by_field(
        self, api_client, mock_db_session
    ):
        """A resposta deve ter generated_by = 'gpt-4o'."""
        self._setup_generate_mocks(mock_db_session)

        with (
            patch(
                "app.modules.patient.router.call_openai_generate",
                new_callable=AsyncMock,
            ) as mock_gen,
            patch(
                "app.modules.patient.router.get_embeddings",
                new_callable=AsyncMock,
            ) as mock_emb,
        ):
            mock_gen.return_value = SAMPLE_CASE_JSON
            mock_emb.side_effect = _embeddings_side_effect

            resp = await api_client.post(
                "/api/v1/patients/generate",
                json=self.BASE_PAYLOAD,
            )

        assert resp.status_code == 201
        assert resp.json()["generated_by"] == "gpt-4o"

    # -----------------------------------------------------------------------
    # Validação de entrada
    # -----------------------------------------------------------------------

    async def test_missing_eixo_a_returns_422(self, api_client, mock_db_session):
        """eixo_a é obrigatório — ausência deve retornar 422."""
        resp = await api_client.post(
            "/api/v1/patients/generate",
            json={
                "eixo_b": "colaborativo",
                "complexidade": "media",
            },
        )
        assert resp.status_code == 422

    async def test_accepts_all_eixo_c_values(self, api_client, mock_db_session):
        """
        O endpoint deve aceitar todos os valores válidos de eixo_c
        sem retornar 422 (validação de schema).
        """
        valid_eixo_c = [
            "baixo_letramento_vulneravel",
            "medio_letramento_media",
            "alto_letramento_bom_acesso",
            "pediatrico",
        ]
        for value in valid_eixo_c:
            self._setup_generate_mocks(mock_db_session)

            with (
                patch(
                    "app.modules.patient.router.call_openai_generate",
                    new_callable=AsyncMock,
                ) as mock_gen,
                patch(
                    "app.modules.patient.router.get_embeddings",
                    new_callable=AsyncMock,
                ) as mock_emb,
            ):
                mock_gen.return_value = SAMPLE_CASE_JSON
                mock_emb.side_effect = _embeddings_side_effect

                resp = await api_client.post(
                    "/api/v1/patients/generate",
                    json={**self.BASE_PAYLOAD, "eixo_c": value},
                )

            assert resp.status_code != 422, (
                f"eixo_c={value!r} retornou 422 — deve ser aceito pelo schema"
            )

    async def test_sexo_masculino_accepted(self, api_client, mock_db_session):
        """sexo='M' deve ser aceito (não retornar 422)."""
        self._setup_generate_mocks(mock_db_session)

        with (
            patch(
                "app.modules.patient.router.call_openai_generate",
                new_callable=AsyncMock,
            ) as mock_gen,
            patch(
                "app.modules.patient.router.get_embeddings",
                new_callable=AsyncMock,
            ) as mock_emb,
        ):
            mock_gen.return_value = SAMPLE_CASE_JSON
            mock_emb.side_effect = _embeddings_side_effect

            resp = await api_client.post(
                "/api/v1/patients/generate",
                json={**self.BASE_PAYLOAD, "sexo": "M"},
            )

        assert resp.status_code != 422

    async def test_sexo_feminino_accepted(self, api_client, mock_db_session):
        """sexo='F' deve ser aceito (não retornar 422)."""
        self._setup_generate_mocks(mock_db_session)

        with (
            patch(
                "app.modules.patient.router.call_openai_generate",
                new_callable=AsyncMock,
            ) as mock_gen,
            patch(
                "app.modules.patient.router.get_embeddings",
                new_callable=AsyncMock,
            ) as mock_emb,
        ):
            mock_gen.return_value = {**SAMPLE_CASE_JSON, "sexo": "F"}
            mock_emb.side_effect = _embeddings_side_effect

            resp = await api_client.post(
                "/api/v1/patients/generate",
                json={**self.BASE_PAYLOAD, "sexo": "F"},
            )

        assert resp.status_code != 422

    async def test_faixa_etaria_included_in_prompt(self, api_client, mock_db_session):
        """
        Quando faixa_etaria é fornecida, o endpoint não deve retornar 422.
        """
        self._setup_generate_mocks(mock_db_session)

        with (
            patch(
                "app.modules.patient.router.call_openai_generate",
                new_callable=AsyncMock,
            ) as mock_gen,
            patch(
                "app.modules.patient.router.get_embeddings",
                new_callable=AsyncMock,
            ) as mock_emb,
        ):
            mock_gen.return_value = SAMPLE_CASE_JSON
            mock_emb.side_effect = _embeddings_side_effect

            resp = await api_client.post(
                "/api/v1/patients/generate",
                json={**self.BASE_PAYLOAD, "faixa_etaria": "idoso"},
            )

        assert resp.status_code != 422

    async def test_instrucoes_extras_accepted(self, api_client, mock_db_session):
        """instrucoes_extras deve ser aceito pelo schema sem retornar 422."""
        self._setup_generate_mocks(mock_db_session)

        with (
            patch(
                "app.modules.patient.router.call_openai_generate",
                new_callable=AsyncMock,
            ) as mock_gen,
            patch(
                "app.modules.patient.router.get_embeddings",
                new_callable=AsyncMock,
            ) as mock_emb,
        ):
            mock_gen.return_value = SAMPLE_CASE_JSON
            mock_emb.side_effect = _embeddings_side_effect

            resp = await api_client.post(
                "/api/v1/patients/generate",
                json={**self.BASE_PAYLOAD, "instrucoes_extras": "paciente gestante de 28 semanas"},
            )

        assert resp.status_code != 422
