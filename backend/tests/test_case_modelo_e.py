# backend/tests/test_case_modelo_e.py
"""Modelo padronizado de casos (modelo E): parser, estruturação, cadastro manual, geração e importação de DOCX."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.patient.case_template import (
    SISTEMAS, build_chunk_sections, label_for, normalize_agente, normalize_exame_fisico,
    normalize_interrogatorio,
)
from app.modules.patient.router import extract_manual_fields, validate_extracted
from app.schemas.patient import CaseData, PatientManualRequest
from scripts.ingest.case_parser import (
    infer_eixo_c, match_heading, parse_case, parse_perfil_eixo_c, quality_report, short_diagnosis,
)
from scripts.ingest.case_structure import build_case_data, structure_agente, structure_medicacoes

MODELO_E = """\
UFPI - CCS - DCG

Metadados do caso (uso interno — não faz parte do roteiro do aluno)

Caso nº: 1   |   Semana de produção: 1

Eixo A — Categoria diagnóstica: Cardiovascular (hipotensão postural em idoso polimedicado; com comorbidade endócrina associada)

Eixo B — Perfil de personalidade/comunicação: Colaborativo | Complexidade Alta (nuance: minimiza sintomas antigos)

Eixo C — Perfil sociodemográfico: Alfonso Pereira dos Santos, 78 anos, masculino | Letramento Baixo | Condição social Baixa | Idoso aposentado, analfabeto funcional

CASO 1 — PACIENTE VIRTUAL

VipLab UFPI

Caso 1 – Apagões ao Levantar em Idoso Polimedicado

Contexto para o aluno

Alfonso, 78 anos. Consultório do posto de saúde, final da manhã.

1. Identificação

Nome: Alfonso Pereira dos Santos

Idade: 78 anos

Sexo: Masculino

Cor (raça): Pardo

Nacionalidade: Brasileira

Escolaridade: Fundamental incompleto

Residências anteriores: Campo Maior – PI

Informante: O próprio paciente

2. Queixa Principal

"Apagão."

3. História da Doença Atual

Paciente relata que há 2 semanas, ao levantar-se da mesa, apresentou turvação visual seguida de síncope, com recuperação espontânea em 1 a 2 minutos.

4. Interrogatório Complementar Relativo a Órgãos e Aparelhos

Cabeça: Nega cefaleia.

Olhos: Turvação visual transitória.

Aparelho respiratório e circulatório: Nega dor torácica.

Sistema hematopoético: Nega sangramentos.

5. Antecedentes Pessoais

5.1 Antecedentes Fisiológicos

Nascido em domicílio, parto assistido por parteira.

5.2 Antecedentes Patológicos

Hipertensão arterial há 20 anos.

Nega alergias medicamentosas conhecidas.

6. Medicações em Uso

Losartana 50 mg — 1 comprimido/dia (tratamento da hipertensão arterial)

Metformina 850 mg — 2 comprimidos/dia (tratamento do diabetes mellitus tipo 2)

Observação: Toma todos juntos pela manhã, em jejum.

7. Antecedentes Familiares

Pai falecido aos 70 anos, de AVC.

8. Hábitos de Vida

Mora com a filha. Nega tabagismo.

9. Exame Físico

Sinais Vitais

PA: 138 x 86 mmHg (deitado)  |  FC: 78 bpm  |  PA em pé (1º minuto): 106 x 68 mmHg  |  Observação: Ao ficar em pé, refere turvação visual. Mantém a queixa.

Exame Físico Geral

Regular estado geral, mucosas discretamente secas.

Aparelho Cardiovascular

Ritmo regular em 2 tempos, sem sopros.

Características do Agente de IA

Alfonso é um paciente colaborativo e educado: responde prontamente ao que lhe é perguntado.

Não relaciona espontaneamente os episódios ao uso dos medicamentos.

Voz, postura e discurso

- Voz baixa e pausada.

Vocabulário

- Usa "apagão" e "cabeça leve".

Reações emocionais

- Calmo e agradecido.

O que omite, minimiza ou distorce

- Afirma que toma os remédios "direitinho".

Temas sensíveis

- Insegurança alimentar.

Desafios de comunicação

- Adaptar a linguagem ao baixo letramento.

Acompanhante

- A filha fica na porta.

Dados revelados só por interrogação ativa

- Uso de todos os medicamentos de uma vez.
"""


@pytest.fixture(scope="module")
def parsed():
    return parse_case(MODELO_E)


class TestParserModeloE:
    def test_numbered_subsections_are_headings(self):
        assert match_heading("5.1 Antecedentes Fisiológicos") == ("historia_fisiologica", True)
        assert match_heading("5.2 Antecedentes Patológicos") == ("historia_patologica", True)
        assert match_heading("6. Medicações em Uso") == ("medicacoes_em_uso", True)
        assert match_heading("Contexto para o aluno") == ("contexto_aluno", False)

    def test_value_with_decimal_is_not_heading(self):
        assert match_heading("1.5 L de água por dia") is None

    def test_sections_split_as_the_template(self, parsed):
        s = parsed["sections"]
        assert s["contexto_aluno"].startswith("Alfonso, 78 anos")
        assert s["historia_fisiologica"].startswith("Nascido em domicílio")
        assert "Hipertensão arterial" in s["historia_patologica"]
        assert "Losartana" not in s["historia_patologica"]  # seção 6 não vaza para a patológica
        assert s["medicacoes_em_uso"].startswith("Losartana 50 mg")
        assert "Fundamental" not in s["contexto_aluno"]

    def test_identificacao_has_new_fields(self, parsed):
        ident = parsed["identificacao"]
        assert ident["nacionalidade"] == "Brasileira"
        assert ident["residencias_anteriores"] == "Campo Maior – PI"
        assert ident["informante"] == "O próprio paciente"
        assert "outros" not in ident

    def test_eixos_complexidade_nuance_and_perfil(self, parsed):
        meta = parsed["metadados"]
        assert meta["complexidade_bruta"] == "Alta"
        assert meta["eixo_b_nuance"] == "minimiza sintomas antigos"
        assert meta["eixo_c_letramento"] == "baixo"
        assert meta["eixo_c_condicao_social"] == "baixa"
        assert meta["eixo_c_descricao"].startswith("Idoso aposentado")
        assert meta["titulo"] == "Apagões ao Levantar em Idoso Polimedicado"  # não "PACIENTE VIRTUAL"

    def test_diagnosis_comes_from_eixo_a_before_semicolon(self, parsed):
        dx = parsed["diagnostico"]
        assert dx["principal"] == "hipotensão postural em idoso polimedicado"
        assert dx["detalhe"] == "com comorbidade endócrina associada"

    def test_quality_has_no_warnings_for_complete_document(self, parsed):
        assert quality_report(parsed)["avisos"] == []

    def test_missing_modelo_e_sections_are_reported(self):
        incompleto = MODELO_E.replace("6. Medicações em Uso", "6. Outros")
        avisos = quality_report(parse_case(incompleto))["avisos"]
        assert any("medicacoes_em_uso" in a for a in avisos)


class TestEixoCModeloE:
    def test_parse_perfil(self):
        p = parse_perfil_eixo_c("Lívio, 8 anos | Letramento Baixo (da mãe, informante) | Condição social Alta | Criança")
        assert p == {"letramento": "baixo", "letramento_observacao": "da mãe, informante",
                     "condicao_social": "alta", "descricao": "Criança"}

    @pytest.mark.parametrize("raw,esperado", [
        ("X, 40 anos | Letramento Alto | Condição social Alta | universitária", "alto_letramento_bom_acesso"),
        ("X, 40 anos | Letramento Médio | Condição social Alta | contadora", "medio_letramento_media"),
        ("X, 40 anos | Letramento Baixo | Condição social Baixa | lavrador", "baixo_letramento_vulneravel"),
    ])
    def test_explicit_letramento_wins(self, raw, esperado):
        assert infer_eixo_c(raw, 40 * 12, "")[0] == esperado

    def test_minor_is_pediatric_even_with_letramento(self):
        assert infer_eixo_c("X, 8 anos | Letramento Baixo | Condição social Alta", 96, "")[0] == "pediatrico"


class TestShortDiagnosis:
    def test_keeps_acronym_and_cuts_detail(self):
        assert short_diagnosis(
            "síndrome da taquicardia postural ortostática — POTS, de provável início pós-viral"
        ) == "Síndrome da taquicardia postural ortostática (POTS)"

    def test_cuts_at_dash_and_comma_qualifier(self):
        assert short_diagnosis("diabetes mellitus tipo 1 — apresentação inicial, sem cetoacidose") == "Diabetes mellitus tipo 1"
        assert short_diagnosis("coledocolitíase com sinais de colangite, em paciente com colelitíase") == \
            "Coledocolitíase com sinais de colangite"


class TestEstruturaModeloE:
    def test_medicacoes_itens_e_observacao(self, parsed):
        m = structure_medicacoes(parsed["sections"]["medicacoes_em_uso"])
        assert m["itens"] == [
            "Losartana 50 mg — 1 comprimido/dia (tratamento da hipertensão arterial)",
            "Metformina 850 mg — 2 comprimidos/dia (tratamento do diabetes mellitus tipo 2)",
        ]
        assert m["observacao"] == "Toma todos juntos pela manhã, em jejum."

    def test_sem_medicacao_vai_para_observacao(self):
        m = structure_medicacoes("Sem medicações de uso regular\n\nObservação: Polivitamínico por conta da mãe.")
        assert m["itens"] == []
        assert m["observacao"].startswith("Sem medicações de uso regular")

    def test_agente_subsecoes(self, parsed):
        a = structure_agente(parsed["sections"]["caracteristicas_agente"])
        assert a["perfil"].startswith("Alfonso é um paciente colaborativo e educado: responde")
        assert a["voz_postura_discurso"] == ["Voz baixa e pausada."]
        assert a["omite_minimiza_distorce"] == ['Afirma que toma os remédios "direitinho".']
        assert a["acompanhante"] == ["A filha fica na porta."]
        assert a["dados_so_por_interrogacao"] == ["Uso de todos os medicamentos de uma vez."]

    def test_agente_texto_corrido_vira_perfil(self):
        assert structure_agente("Paciente ansioso, fala rápido.") == {"perfil": "Paciente ansioso, fala rápido."}

    def test_case_data_v3_e_valida_no_schema(self, parsed):
        ident = dict(parsed["identificacao"])
        classificacao = {
            "eixo_a": "cardiovascular", "eixo_b": "colaborativo", "eixo_c": "baixo_letramento_vulneravel",
            "complexidade": "alta", "fontes": {}, "letramento": "baixo", "condicao_social": "baixa",
            "diagnostico_principal_curto": "Hipotensão postural", "diagnostico_curado": None,
        }
        cd = build_case_data(parsed, ident_final=ident, classificacao=classificacao,
                             qualidade=quality_report(parsed), arquivo="Caso 1.docx")
        assert cd["schema_version"] == 3
        assert cd["contexto_aluno"].startswith("Alfonso")
        assert cd["historia_patologica"]["medicamentos_em_uso"][0].startswith("Losartana")
        assert cd["historia_patologica"]["medicacoes_observacao"].startswith("Toma todos juntos")
        assert cd["historia_fisiologica"]["texto_livre"].startswith("Nascido")
        assert cd["exame_fisico"]["sinais_vitais"]["observacao"].startswith("Ao ficar em pé")
        assert cd["exame_fisico"]["sinais_vitais"]["pa_em_pe_1o_minuto"] == "106 x 68 mmHg"
        assert cd["classificacao"]["letramento"] == "baixo"
        CaseData(**cd)


class TestCaseTemplate:
    def test_interrogatorio_dict_e_legado(self):
        est, texto = normalize_interrogatorio({"cabeca": "Nega cefaleia.", "olhos": "  "})
        assert est == {"cabeca": "Nega cefaleia."}
        assert texto == "Cabeça: Nega cefaleia."
        assert normalize_interrogatorio("Nega tosse.") == ({"texto": "Nega tosse."}, "Nega tosse.")

    def test_exame_fisico_dict_gera_texto(self):
        est, texto = normalize_exame_fisico({
            "sinais_vitais": {"pa": "120 x 80 mmHg", "observacao": "em pé: 100 x 60"},
            "aparelho_cardiovascular": "RCR 2T",
        })
        assert est["sinais_vitais"]["pa"] == "120 x 80 mmHg"
        assert est["texto_livre"] == texto
        assert "Aparelho cardiovascular: RCR 2T" in texto
        assert "Observação: em pé: 100 x 60" in texto

    def test_agente_dict_e_texto(self):
        est, texto = normalize_agente({"perfil": "Colaborativo.", "vocabulario": "- termo A\n- termo B", "temas_sensiveis": []})
        assert est == {"perfil": "Colaborativo.", "vocabulario": ["termo A", "termo B"]}
        assert "Vocabulário\n- termo A\n- termo B" in texto
        assert normalize_agente("texto antigo") == ({"perfil": "texto antigo"}, "texto antigo")

    def test_label_for_cobre_chaves_novas_e_antigas(self):
        assert label_for("aparelho_respiratorio_e_circulatorio") == "Aparelho respiratório e circulatório"
        assert label_for("aparelho_respiratorio_circulatorio") == "Aparelho respiratório e circulatório"
        assert label_for("pa_em_pe_1o_minuto") == "PA em pe 1o minuto"
        assert len({k for k, _ in SISTEMAS}) == len(SISTEMAS) == 19

    def test_chunk_sections_incluem_contexto_e_medicacoes(self):
        cd = {
            "identificacao": {"nome": "A", "idade": 5, "sexo": "M", "informante": "Mãe"},
            "contexto_aluno": "Consultório.",
            "historia_patologica": {"medicamentos_em_uso": ["X 5 mg"], "medicacoes_observacao": "Toma errado"},
            "caracteristicas_agente": "Perfil",
        }
        s = build_chunk_sections(cd, ["H1", "H2"])
        assert s["contexto_aluno"] == "Consultório."
        assert "Informante: Mãe" in s["identificacao"]
        assert s["medicacoes_em_uso"] == "X 5 mg\nObservação: Toma errado"
        assert s["hipoteses_diagnosticas"] == "H1 | H2"


# ── Endpoints ────────────────────────────────────────────────────────────────

pytestmark_async = pytest.mark.asyncio

HDA = "Paciente relata síncope ao levantar-se há 2 semanas, com turvação visual prévia e recuperação espontânea."

PAYLOAD_E = {
    "eixo_a": "cardiovascular", "nome": "Alfonso Pereira", "idade": 78, "sexo": "M",
    "queixa_principal": "Apagão", "diagnostico_principal": "Hipotensão postural",
    "letramento": "baixo", "condicao_social": "baixa", "nuance_eixo_b": "minimiza sintomas",
    "nacionalidade": "Brasileira", "escolaridade": "Fundamental incompleto", "informante": "O próprio",
    "contexto_aluno": "Consultório do posto, final da manhã.",
    "historia_doenca_atual": HDA,
    "interrogatorio_complementar": {"cabeca": "Nega cefaleia.", "olhos": "Turvação visual."},
    "historia_fisiologica": "Parto domiciliar.",
    "medicamentos_em_uso": ["Losartana 50 mg — 1 comprimido/dia"],
    "medicacoes_observacao": "Toma tudo junto, em jejum.",
    "exame_fisico": {"sinais_vitais": {"pa": "138 x 86 mmHg"}, "aparelho_cardiovascular": "RCR 2T"},
    "agente_ia": {"perfil": "Colaborativo.", "vocabulario": ["apagão"]},
}


def _rows(rows):
    r = MagicMock()
    r.fetchall.return_value = rows
    return r


async def _emb(texts):
    return [[0.0] * 1536 for _ in texts]


@pytest.mark.asyncio
class TestManualModeloE:
    async def _post(self, api_client, mock_db_session, payload):
        mock_db_session.execute.return_value = _rows([(1,)])
        with patch("app.modules.patient.router.get_embeddings", side_effect=_emb):
            return await api_client.post("/api/v1/patients/manual", json=payload)

    async def test_case_data_segue_o_modelo(self, api_client, mock_db_session):
        resp = await self._post(api_client, mock_db_session, PAYLOAD_E)
        assert resp.status_code == 201, resp.text
        cd = resp.json()["patient"]["case_data"]
        assert cd["schema_version"] == 3
        assert cd["contexto_aluno"].startswith("Consultório")
        assert cd["identificacao"]["nacionalidade"] == "Brasileira"
        assert cd["identificacao"]["informante"] == "O próprio"
        assert cd["interrogatorio_complementar"] == {"cabeca": "Nega cefaleia.", "olhos": "Turvação visual."}
        assert cd["exame_fisico"]["sinais_vitais"] == {"pa": "138 x 86 mmHg"}
        assert "RCR 2T" in cd["exame_fisico"]["texto_livre"]
        assert cd["historia_patologica"]["medicacoes_observacao"] == "Toma tudo junto, em jejum."
        assert cd["agente_ia"] == {"perfil": "Colaborativo.", "vocabulario": ["apagão"]}
        assert "Vocabulário" in cd["caracteristicas_agente"]
        assert cd["classificacao"]["letramento"] == "baixo"
        assert cd["classificacao"]["nuance_eixo_b"] == "minimiza sintomas"
        CaseData(**cd)

    async def test_formato_antigo_com_texto_unico_continua_valido(self, api_client, mock_db_session):
        payload = {**PAYLOAD_E, "interrogatorio_complementar": "Nega tosse.", "exame_fisico": "PA 120/80.",
                   "caracteristicas_agente": "Paciente calmo."}
        del payload["agente_ia"]
        resp = await self._post(api_client, mock_db_session, payload)
        assert resp.status_code == 201, resp.text
        cd = resp.json()["patient"]["case_data"]
        assert cd["interrogatorio_complementar"] == {"texto": "Nega tosse."}
        assert cd["exame_fisico"]["texto_livre"] == "PA 120/80."
        assert cd["caracteristicas_agente"] == "Paciente calmo."

    async def test_chunks_por_secao_incluem_contexto_e_medicacoes(self, api_client, mock_db_session):
        resp = await self._post(api_client, mock_db_session, PAYLOAD_E)
        sections = {c.args[0].section for c in mock_db_session.add.call_args_list if hasattr(c.args[0], "section")}
        assert {"contexto_aluno", "medicacoes_em_uso", "interrogatorio_complementar", "exame_fisico"} <= sections

    @pytest.mark.parametrize("campo,valor", [("letramento", "enorme"), ("condicao_social", "x")])
    async def test_letramento_e_condicao_invalidos_422(self, api_client, mock_db_session, campo, valor):
        assert (await self._post(api_client, mock_db_session, {**PAYLOAD_E, campo: valor})).status_code == 422


GENERATED_E = {
    "nome": "Maria Souza", "idade": 64, "sexo": "F", "queixa_principal": "Dor na barriga",
    "diagnostico_principal": "Coledocolitíase",
    "contexto_aluno": "Posto de saúde, tarde.",
    "identificacao": {"cor": "parda", "nacionalidade": "Brasileira", "informante": "A própria"},
    "historia_doenca_atual": "Dor em hipocôndrio direito há 3 dias, com febre e icterícia progressiva.",
    "interrogatorio_complementar": {"cabeca": "Nega cefaleia.", "aparelho_digestivo": "Náuseas."},
    "historia_fisiologica": "Menopausa aos 50.",
    "historia_patologica": {"medicamentos_em_uso": ["Losartana 50 mg — 1 cp/dia"], "medicacoes_observacao": "Toma certo.",
                            "texto_livre": "HAS."},
    "historia_familiar": "Mãe com DM2.",
    "historia_social": {"texto_livre": "Mora sozinha."},
    "exame_fisico": {"sinais_vitais": {"pa": "130 x 80 mmHg"}, "aparelho_abdominal": "Dor em HCD."},
    "hipoteses_diagnosticas": ["Coledocolitíase", "Colecistite"],
    "agente_ia": {"perfil": "Enlutada.", "temas_sensiveis": ["viuvez"], "acompanhante": []},
}


@pytest.mark.asyncio
class TestGenerateModeloE:
    async def test_agente_estruturado_e_novos_campos(self, api_client, mock_db_session):
        mock_db_session.execute.return_value = _rows([])
        with patch("app.modules.patient.router.call_openai_generate", new_callable=AsyncMock) as gen, \
                patch("app.modules.patient.router.get_embeddings", side_effect=_emb):
            gen.return_value = GENERATED_E
            resp = await api_client.post("/api/v1/patients/generate", json={
                "eixo_a": "gastrointestinal", "condicao_social": "media"})
        assert resp.status_code == 201, resp.text
        cd = resp.json()["patient"]["case_data"]
        assert cd["schema_version"] == 3 and cd["gerado_por_llm"] is True
        assert cd["agente_ia"] == {"perfil": "Enlutada.", "temas_sensiveis": ["viuvez"]}
        assert "Temas sensíveis" in cd["caracteristicas_agente"]
        assert cd["contexto_aluno"] == "Posto de saúde, tarde."
        assert cd["identificacao"]["informante"] == "A própria"
        assert cd["historia_patologica"]["medicacoes_observacao"] == "Toma certo."
        assert cd["classificacao"]["condicao_social"] == "media"
        CaseData(**cd)

    async def test_condicao_social_invalida_422(self, api_client, mock_db_session):
        resp = await api_client.post("/api/v1/patients/generate", json={"eixo_a": "cardiovascular", "condicao_social": "x"})
        assert resp.status_code == 422

    def test_prompt_pede_modelo_padronizado(self):
        from app.modules.patient.router import GENERATION_SYSTEM_PROMPT, build_user_prompt
        from app.schemas.patient import PatientGenerateRequest
        for chave in ("contexto_aluno", "agente_ia", "medicacoes_observacao", "aparelho_genito_urinario",
                      "sistema_hematopoetico", "aparelho_osteoarticular", "dados_so_por_interrogacao"):
            assert chave in GENERATION_SYSTEM_PROMPT
        req = PatientGenerateRequest(eixo_a="cardiovascular", condicao_social="alta")
        assert "Condição social: alta" in build_user_prompt(req)
        assert "Condição social:" not in build_user_prompt(PatientGenerateRequest(eixo_a="cardiovascular"))


class TestImportDocxModeloE:
    def test_extract_gera_payload_valido_para_o_formulario(self):
        ex = extract_manual_fields(MODELO_E)
        assert ex["nome"] == "Alfonso Pereira dos Santos"
        assert ex["eixo_a"] == "cardiovascular" and ex["complexidade"] == "alta"
        assert ex["letramento"] == "baixo" and ex["condicao_social"] == "baixa"
        assert ex["nuance_eixo_b"] == "minimiza sintomas antigos"
        assert ex["diagnostico_principal"] == "Hipotensão postural em idoso polimedicado"
        assert ex["contexto_aluno"].startswith("Alfonso")
        assert ex["medicamentos_em_uso"][0].startswith("Losartana")
        assert ex["medicacoes_observacao"].startswith("Toma todos juntos")
        assert ex["interrogatorio_complementar"]["cabeca"] == "Nega cefaleia."
        assert ex["exame_fisico"]["sinais_vitais"]["pa"].startswith("138 x 86")
        assert ex["agente_ia"]["vocabulario"] == ['Usa "apagão" e "cabeça leve".']
        PatientManualRequest(**{k: v for k, v in ex.items() if v not in ("", None, [])})

    def test_validacao_aponta_sistemas_e_subsecoes_ausentes(self):
        issues = validate_extracted(extract_manual_fields(MODELO_E))
        msgs = {i.field: i.message for i in issues}
        assert not [i for i in issues if i.severity == "error"]
        assert "Língua" in msgs["interrogatorio_complementar"]  # o fixture só traz 4 dos 19 sistemas
        assert "agente_ia" not in msgs  # todas as subseções esperadas presentes

    def test_documento_sem_secoes_do_modelo_gera_avisos(self):
        issues = validate_extracted(extract_manual_fields("1. Identificação\nNome: Ana\nIdade: 30 anos\nSexo: F"))
        fields = {i.field for i in issues}
        assert {"contexto_aluno", "agente_ia", "medicamentos_em_uso"} <= fields
