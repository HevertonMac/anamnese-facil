# backend/tests/test_api_parse_docx.py
"""Testes de POST /api/v1/patients/parse-docx (pré-visualização, não grava no banco).

O pandoc é mockado (docx_to_text chama subprocess.run), então os testes não dependem dele instalado.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.asyncio

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

CASE_TEXT = """\
Metadados do caso
Eixo A (Categoria diagnóstica): Cardiovascular
Eixo B (Perfil de comunicação): Colaborativo
Complexidade: Média

1. Identificação
Nome: João Cardoso
Idade: 55 anos
Sexo: Masculino
Cor: Parda
Profissão: Agricultor

2. Queixa principal
Dor no peito ao esforço

3. História da doença atual
Paciente relata dor precordial em aperto há dois meses, desencadeada por esforço moderado e aliviada com o repouso, sem irradiação.

9. Exame Físico
PA: 145/90 mmHg. FC: 78 bpm.

Diagnóstico principal (não informar ao aluno):
Angina Estável
"""


def _upload(name="caso.docx", content=b"PK-fake"):
    return {"file": (name, content, DOCX_MIME)}


class _Completed:
    def __init__(self, stdout):
        self.stdout = stdout


class TestParseDocx:
    async def test_arquivo_nao_docx_retorna_400(self, api_client):
        resp = await api_client.post("/api/v1/patients/parse-docx", files=_upload("caso.pdf"))
        assert resp.status_code == 400

    async def test_docx_valido_retorna_campos_e_issues(self, api_client):
        with patch("subprocess.run", return_value=_Completed(CASE_TEXT)):
            resp = await api_client.post("/api/v1/patients/parse-docx", files=_upload())
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert {"extracted", "issues", "can_save"} <= body.keys()
        assert body["extracted"]["nome"] == "João Cardoso"
        assert body["extracted"]["idade"] == 55
        assert body["extracted"]["sexo"] == "M"
        assert body["extracted"]["eixo_a"] == "cardiovascular"
        assert all({"field", "severity", "message"} <= i.keys() for i in body["issues"])

    async def test_campos_obrigatorios_ausentes_geram_erro(self, api_client):
        with patch("subprocess.run", return_value=_Completed("Texto solto sem seções reconhecíveis.")):
            resp = await api_client.post("/api/v1/patients/parse-docx", files=_upload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["can_save"] is False
        error_fields = {i["field"] for i in body["issues"] if i["severity"] == "error"}
        assert {"nome", "historia_doenca_atual", "queixa_principal"} <= error_fields

    async def test_pandoc_indisponivel_retorna_500_legivel(self, api_client):
        with patch("subprocess.run", side_effect=FileNotFoundError("pandoc")):
            resp = await api_client.post("/api/v1/patients/parse-docx", files=_upload())
        assert resp.status_code == 500
        assert "pandoc" in resp.json()["detail"].lower()
