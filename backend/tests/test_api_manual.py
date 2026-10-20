# backend/tests/test_api_manual.py
"""Testes de POST /api/v1/patients/manual (cadastro manual, sem LLM)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio

HDA = (
    "Paciente relata dor precordial em aperto há dois meses, desencadeada por esforço "
    "moderado e aliviada com o repouso, sem irradiação."
)

VALID_PAYLOAD = {
    "eixo_a": "cardiovascular",
    "nome": "João Cardoso",
    "idade": 55,
    "sexo": "M",
    "queixa_principal": "Dor no peito ao esforço",
    "diagnostico_principal": "Angina Estável",
    "historia_doenca_atual": HDA,
    "medicamentos_em_uso": ["Losartana 50mg 1x/dia"],
    "hipoteses_diagnosticas": ["Angina Estável"],
}


def _execute_result(rows=None):
    result = MagicMock()
    result.fetchall.return_value = rows if rows is not None else []
    return result


async def _fake_embeddings(texts):
    return [[0.0] * 1536 for _ in texts]


@pytest.fixture
def post_manual(api_client, mock_db_session):
    mock_db_session.execute.return_value = _execute_result([(1,), (2,)])

    async def _post(payload):
        with patch("app.modules.patient.router.get_embeddings", side_effect=_fake_embeddings):
            return await api_client.post("/api/v1/patients/manual", json=payload)

    return _post


class TestCreatePatientManual:
    async def test_payload_valido_retorna_201(self, post_manual):
        resp = await post_manual(VALID_PAYLOAD)
        assert resp.status_code == 201, resp.text

    async def test_resposta_tem_campos_esperados(self, post_manual):
        body = (await post_manual(VALID_PAYLOAD)).json()
        assert body["patient"]["nome"] == "João Cardoso"
        assert body["patient"]["case_number"] == 3  # existentes: 1 e 2
        assert body["chunks_ingested"] > 0
        assert body["generated_by"] == "manual"

    async def test_case_data_montado_sem_llm(self, post_manual):
        case_data = (await post_manual(VALID_PAYLOAD)).json()["patient"]["case_data"]
        assert case_data["gerado_por_llm"] is False
        assert case_data["queixa_principal_texto"] == VALID_PAYLOAD["queixa_principal"]
        assert case_data["historia_patologica"]["medicamentos_em_uso"] == ["Losartana 50mg 1x/dia"]

    async def test_sem_nome_retorna_422(self, post_manual):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "nome"}
        assert (await post_manual(payload)).status_code == 422

    async def test_sem_eixo_a_retorna_422(self, post_manual):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "eixo_a"}
        assert (await post_manual(payload)).status_code == 422

    async def test_hda_curta_retorna_422(self, post_manual):
        resp = await post_manual({**VALID_PAYLOAD, "historia_doenca_atual": "Dor no peito."})
        assert resp.status_code == 422

    @pytest.mark.parametrize("sexo", ["X", "m", "", "Masculino"])
    async def test_sexo_invalido_retorna_422(self, post_manual, sexo):
        assert (await post_manual({**VALID_PAYLOAD, "sexo": sexo})).status_code == 422
