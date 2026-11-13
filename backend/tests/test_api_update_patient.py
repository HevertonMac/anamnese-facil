# backend/tests/test_api_update_patient.py
"""Testes de PUT /api/v1/patients/{id} (edição de paciente, somente administradores)."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from conftest import make_patient
from test_api_manual import VALID_PAYLOAD

pytestmark = pytest.mark.asyncio

EDIT_PAYLOAD = {
    **VALID_PAYLOAD,
    "nome": "João Cardoso Editado",
    "idade": 60,
    "eixo_a": "clinica_cirurgica",
    "eixo_a_secundario": "cardiovascular",
}


def _as_user(role: str):
    from app.main import app
    from app.modules.auth.router import get_current_user

    user = MagicMock()
    user.role = role
    user.email = f"{role}@test.com"
    app.dependency_overrides[get_current_user] = lambda: user


def _found(db, patient):
    result = MagicMock()
    result.scalar_one_or_none.return_value = patient
    db.execute = AsyncMock(return_value=result)


async def _fake_embeddings(texts):
    return [[0.0] * 1536 for _ in texts]


async def _put(api_client, patient_id, payload, embeddings=_fake_embeddings):
    with patch("app.modules.patient.router.get_embeddings", side_effect=embeddings):
        return await api_client.put(f"/api/v1/patients/{patient_id}", json=payload)


class TestUpdatePatientAuth:
    async def test_requires_authentication(self, api_client):
        resp = await api_client.put(f"/api/v1/patients/{uuid.uuid4()}", json=EDIT_PAYLOAD)
        assert resp.status_code in (401, 403)

    @pytest.mark.parametrize("role", ["student", "teacher"])
    async def test_non_admin_forbidden(self, api_client, mock_db_session, role):
        _as_user(role)
        resp = await _put(api_client, uuid.uuid4(), EDIT_PAYLOAD)
        assert resp.status_code == 403
        mock_db_session.commit.assert_not_called()


class TestUpdatePatient:
    async def test_patient_not_found(self, api_client, mock_db_session):
        _as_user("admin")
        _found(mock_db_session, None)
        resp = await _put(api_client, uuid.uuid4(), EDIT_PAYLOAD)
        assert resp.status_code == 404
        mock_db_session.commit.assert_not_called()

    async def test_admin_updates_patient(self, api_client, mock_db_session):
        _as_user("admin")
        patient = make_patient(case_number=7)
        _found(mock_db_session, patient)

        resp = await _put(api_client, patient.id, EDIT_PAYLOAD)
        assert resp.status_code == 200, resp.text

        # colunas atualizadas, case_number preservado
        assert patient.nome == "João Cardoso Editado"
        assert patient.idade == 60
        assert patient.eixo_a == "clinica_cirurgica"
        assert patient.eixo_a_secundario == "cardiovascular"
        assert patient.case_number == 7
        # case_data em sincronia com as colunas
        cd = patient.case_data
        assert cd["identificacao"]["nome"] == "João Cardoso Editado"
        assert cd["classificacao"]["eixo_a"] == "clinica_cirurgica"
        assert cd["queixa_principal_texto"] == EDIT_PAYLOAD["queixa_principal"]
        # chunks antigos apagados (select + delete) e novos inseridos, 1 commit
        assert mock_db_session.execute.await_count == 2
        mock_db_session.flush.assert_awaited()
        assert mock_db_session.add.call_count > 0
        mock_db_session.commit.assert_awaited_once()

    async def test_preserva_raw_sections_da_ingestao(self, api_client, mock_db_session):
        _as_user("admin")
        patient = make_patient()
        old_raw = patient.case_data["raw_sections"]
        _found(mock_db_session, patient)

        resp = await _put(api_client, patient.id, EDIT_PAYLOAD)
        assert resp.status_code == 200, resp.text
        assert patient.case_data["raw_sections"] == old_raw

    async def test_remove_segunda_area_quando_vazia(self, api_client, mock_db_session):
        _as_user("admin")
        patient = make_patient(eixo_a_secundario="psiquiatria_saude_mental")
        _found(mock_db_session, patient)

        resp = await _put(api_client, patient.id, {**EDIT_PAYLOAD, "eixo_a_secundario": ""})
        assert resp.status_code == 200, resp.text
        assert patient.eixo_a_secundario is None

    async def test_falha_de_embeddings_retorna_502_sem_alterar(self, api_client, mock_db_session):
        _as_user("admin")
        patient = make_patient(nome="Original")
        _found(mock_db_session, patient)

        async def boom(texts):
            raise HTTPException(status_code=502, detail="Falha ao gerar embeddings na OpenAI.")

        resp = await _put(api_client, patient.id, EDIT_PAYLOAD, embeddings=boom)
        assert resp.status_code == 502
        assert patient.nome == "Original"
        assert mock_db_session.execute.await_count == 1  # só o select; nenhum delete
        mock_db_session.commit.assert_not_called()

    async def test_erro_ao_gravar_faz_rollback_e_retorna_500(self, api_client, mock_db_session):
        _as_user("admin")
        patient = make_patient()
        _found(mock_db_session, patient)
        mock_db_session.commit.side_effect = RuntimeError("db down")

        resp = await _put(api_client, patient.id, EDIT_PAYLOAD)
        assert resp.status_code == 500
        mock_db_session.rollback.assert_awaited_once()


class TestUpdatePatientValidation:
    @pytest.mark.parametrize(
        "override",
        [
            {"eixo_a_secundario": "clinica_cirurgica"},      # igual à principal
            {"eixo_a": "inexistente"},
            {"eixo_a_secundario": "inexistente"},
            {"eixo_b": "inexistente"},
            {"eixo_c": "inexistente"},
            {"complexidade": "inexistente"},
            {"nome": "x" * 101},                              # > String(100) do banco
            {"historia_doenca_atual": "curta"},
            {"sexo": "X"},
        ],
    )
    async def test_payload_invalido_retorna_422(self, api_client, mock_db_session, override):
        _as_user("admin")
        patient = make_patient()
        _found(mock_db_session, patient)
        resp = await _put(api_client, patient.id, {**EDIT_PAYLOAD, **override})
        assert resp.status_code == 422
        mock_db_session.commit.assert_not_called()
