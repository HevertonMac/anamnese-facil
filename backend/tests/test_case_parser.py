# backend/tests/test_case_parser.py
"""
Testes do parser/estruturação dos casos clínicos (scripts/ingest) — sem banco, sem HTTP, sem pandoc.

Os textos de exemplo reproduzem os formatos reais dos .docx:
  modelo A (seções numeradas, ex. casos 1-15 e 41-60), modelo C (casos 21-35: "Hipótese Diagnóstica"),
  modelo D (casos 36-40: sem seção de identificação).
"""
from __future__ import annotations

import pytest

from scripts.ingest.case_parser import (
    SECOES_RESTRITAS,
    SECTION_ALIASES,
    bullets,
    chunk_text,
    infer_eixo_c,
    labeled_blocks,
    map_complexidade,
    map_eixo_a,
    map_eixo_b,
    match_heading,
    parse_case,
    parse_diagnostico,
    parse_idade,
    parse_identificacao,
    parse_metadados,
    quality_report,
    short_diagnosis,
    split_sections,
)
from scripts.ingest.case_structure import (
    build_case_data,
    parse_sinais_vitais,
    structure_exame_fisico,
    structure_interrogatorio,
    structure_patologica,
)

MODELO_A = """\
UFPI - CCS - DCG

Metadados do caso (uso interno — não faz parte do roteiro do aluno)

Caso n: 41 | Semana de produção: 5

Eixo A — Categoria diagnóstica: Gastrointestinal

Eixo B — Perfil de personalidade/comunicação: Baixa adesão / descrente do sistema

Eixo C — Perfil sociodemográfico: Trabalhador informal, letramento médio, adulto idoso, masculino

Caso 41 — Dor Abdominal Recorrente

1. Identificação

Nome: José Raimundo Soares

Idade: 62 anos

Sexo: Masculino

Escolaridade: Ensino Fundamental incompleto

2. Queixa Principal

"Essa dor de barriga que não para."

(Dito com voz rouca. Creuza acrescenta: "ele gemeu a noite toda".)

3. História da Doença Atual

Três internações por dor abdominal nos últimos 7 anos.

4. Interrogatório Complementar Relativo a Órgãos e Aparelhos

Cabeça: Sem queixas.

Digestivo: Esteatorreia relatada somente quando perguntado.

9. Exame Físico

Estado geral:

Mau estado geral, emagrecido.

Dados vitais:

PA: 108/70 mmHg. FC: 88 bpm, rítmica. Tax: 37,3°C. SpO2: 95% em ar ambiente.

Abdome:

Dor à palpação em epigástrio.

Características do Agente de IA

Perfil do agente — José Raimundo:

Dado protegido — esteatorreia: só emerge se perguntado.

Queixa principal:

(checklist, não deve sobrescrever a seção real)
"""

MODELO_C = """\
1. Identificação

Nome: Débora Sampaio Freitas

2. Queixa Principal

"Tô com um cansaço que não passa."

3. História da Doença Atual

Cansaço há 9 meses.

9. Exame Físico (para contextualização do agente — não revelado espontaneamente)

Estado geral: Bom estado geral.

10. Hipótese Diagnóstica

Diagnóstico principal: EVALI — Lesão Pulmonar Associada ao Vaping

Critérios diagnósticos aplicáveis:

1. Uso de vaping nos 90 dias anteriores
2. Infiltrados pulmonares bilaterais
3. Exclusão de causas infecciosas alternativas

Diagnósticos diferenciais principais: Pneumonia atípica; Tromboembolismo pulmonar

11. Características do Agente de IA para Simulação

Minimiza sintomas.

12. Objetivos Educacionais

• Reconhecer EVALI
• Investigar uso de vaping

13. Referências Bibliográficas

CDC. Outbreak of lung injury, 2019.
"""

MODELO_D = """\
PACIENTE VIRTUAL — CASO 36

Eixo A: Musculoesquelético / Reumatológico

Eixo B: Perfil comunicacional: Resistente / Hostil

Eixo C: Mulher, 48 anos, parda — ensino médio completo — renda baixa

Diagnóstico principal: Síndrome do Túnel do Carpo bilateral (forma moderada a grave)

Queixa principal: Fraqueza e dormência nas mãos

2. CONTEXTO CLÍNICO PARA O FACILITADOR

Resumo do caso

Maria das Dores Pereira Lima, 48 anos, costureira há 26 anos.

3. QUEIXA PRINCIPAL

"Minhas mãos estão fracas."

4. HISTÓRIA DA DOENÇA ATUAL

Dormência noturna.
"""


# ── Títulos de seção ──────────────────────────────────────────────────────────

class TestMatchHeading:
    @pytest.mark.parametrize("line,key", [
        ("1. Identificação", "identificacao"),
        ("1. IDENTIFICAÇÃO", "identificacao"),
        ("1. Identificacao", "identificacao"),
        ("3. HISTÓRIA DA DOENÇA ATUAL (HDA)", "historia_doenca_atual"),
        ("4. Interrogatório Complementar Relativo a Órgãos e Aparelhos", "interrogatorio_complementar"),
        ("4. INTERROGATÓRIO COMPLEMENTAR POR ÓRGÃOS E APARELHOS (ICOA)", "interrogatorio_complementar"),
        ("8. REVISÃO DE SISTEMAS", "interrogatorio_complementar"),
        ("5. Antecedentes Pessoais", "historia_patologica"),
        ("6. HISTÓRIA PATOLÓGICA PREGRESSA (HPP)", "historia_patologica"),
        ("6. Antecedentes Obstétricos e Ginecológicos", "antecedentes_gineco_obstetricos"),
        ("6. Antecedentes — Não se aplica (paciente masculino)", "antecedentes_gineco_obstetricos"),
        ("6. Observações Específicas (Cardiovascular)", "observacoes_especificas"),
        ("8. História Social e Hábitos de Vida", "historia_social"),
        ("7. HÁBITOS DE VIDA", "historia_social"),
        ("9. Exame Físico (a ser realizado pelo estudante)", "exame_fisico"),
        ("9. Exame Físico (para contextualização do agente — não revelado espontaneamente)", "exame_fisico"),
        ("10. Hipótese Diagnóstica", "hipoteses_diagnosticas"),
        ("11. Características do Agente de IA — Instruções de Simulação", "caracteristicas_agente"),
        ("11. ROTEIRO DE COMUNICAÇÃO / PERFIL COMPORTAMENTAL", "caracteristicas_agente"),
        ("12. Objetivos Educacionais", "objetivos_educacionais"),
        ("12. OBJETIVOS DE APRENDIZAGEM", "objetivos_educacionais"),
        ("13. Referências Bibliográficas", "referencias"),
        ("2. CONTEXTO CLÍNICO PARA O FACILITADOR", "contexto_facilitador"),
    ])
    def test_numbered_variants(self, line, key):
        assert match_heading(line) == (key, True)

    def test_unnumbered_agent_heading(self):
        assert match_heading("Características do Agente de IA") == ("caracteristicas_agente", False)

    def test_unnumbered_diagnostico_heading_only_when_alone(self):
        assert match_heading("Diagnóstico principal (não informar ao aluno):") == ("diagnostico", False)
        assert match_heading("Diagnóstico principal: Síndrome do Túnel do Carpo") is None

    def test_unnumbered_exame_fisico_alone(self):
        assert match_heading("Exame Físico") == ("exame_fisico", False)
        assert match_heading("Exame Físico Geral") is None

    def test_numbered_list_item_is_not_heading(self):
        assert match_heading("3. Exclusão de causas infecciosas alternativas") is None
        assert match_heading("1. Reconhecer sinais de alarme para neoplasia") is None

    def test_prose_is_not_heading(self):
        assert match_heading("Paciente refere diagnóstico prévio de hipertensão.") is None
        assert match_heading("") is None

    def test_colon_suffixed_uppercase_heading(self):
        assert match_heading("QUEIXA PRINCIPAL:") == ("queixa_principal", False)

    def test_aliases_use_normalized_prefixes(self):
        for prefix, _ in SECTION_ALIASES:
            assert prefix == prefix.lower() and all(c.isalnum() or c == " " for c in prefix)


class TestSplitSections:
    def test_modelo_a_sections(self):
        s = split_sections(MODELO_A)
        for key in ("metadados", "identificacao", "queixa_principal", "historia_doenca_atual",
                    "interrogatorio_complementar", "exame_fisico", "caracteristicas_agente"):
            assert key in s, key

    def test_checklist_queixa_does_not_override_real_section(self):
        s = split_sections(MODELO_A)
        assert "Essa dor de barriga" in s["queixa_principal"]
        assert "checklist" not in s["queixa_principal"]

    def test_stage_directions_stay_in_queixa(self):
        assert "voz rouca" in split_sections(MODELO_A)["queixa_principal"]

    def test_agent_section_not_merged_into_exame_fisico(self):
        s = split_sections(MODELO_A)
        assert "Dado protegido" not in s["exame_fisico"]
        assert "Dado protegido" in s["caracteristicas_agente"]

    def test_modelo_c_list_items_stay_inside_hipoteses(self):
        s = split_sections(MODELO_C)
        assert "Exclusão de causas infecciosas" in s["hipoteses_diagnosticas"]
        assert "Pneumonia atípica" in s["hipoteses_diagnosticas"]
        assert "Minimiza sintomas" in s["caracteristicas_agente"]
        assert "Reconhecer EVALI" in s["objetivos_educacionais"]
        assert "CDC" in s["referencias"]

    def test_modelo_d_header_becomes_metadados(self):
        s = split_sections(MODELO_D)
        assert "Eixo A" in s["metadados"]
        assert "Maria das Dores" in s["contexto_facilitador"]
        assert "identificacao" not in s

    def test_no_text_lost_between_sections(self):
        raw = MODELO_C
        s = split_sections(raw)
        joined = "\n".join(s.values())
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped and match_heading(line) is None:
                assert stripped in joined, f"texto perdido: {stripped!r}"

    def test_old_style_colon_headings(self):
        s = split_sections("IDENTIFICAÇÃO:\nNome: João.\n\nQUEIXA PRINCIPAL:\nDor.\n\nDIAGNÓSTICO:\nAngina.\n")
        assert "João" in s["identificacao"]
        assert s["queixa_principal"] == "Dor."
        assert s["diagnostico"] == "Angina."


# ── Identificação ─────────────────────────────────────────────────────────────

class TestIdentificacao:
    def test_basic_fields(self):
        i = parse_identificacao("Nome: João Cardoso\nIdade: 55 anos\nSexo: Masculino\nCor (raça): Parda\nEstado civil: Casado")
        assert i["nome"] == "João Cardoso"
        assert i["idade"] == 55 and isinstance(i["idade"], int)
        assert i["sexo"] == "M"
        assert i["cor"] == "Parda"
        assert i["estado_civil"] == "Casado"

    def test_feminino(self):
        assert parse_identificacao("Nome: Maria\nIdade: 30\nSexo: Feminino")["sexo"] == "F"

    def test_unknown_values_are_absent_not_invented(self):
        i = parse_identificacao("Idade: não informada\nSexo: indefinido")
        assert "idade" not in i and "sexo" not in i

    def test_unknown_labels_are_kept(self):
        i = parse_identificacao("Nome: Ana\nContato de emergência: Creuza")
        assert i["outros"]["Contato de emergência"] == "Creuza"

    def test_multiline_value_is_joined(self):
        i = parse_identificacao("Residência atual: Bairro São Joaquim\ncasa própria de alvenaria")
        assert "alvenaria" in i["residencia"]

    @pytest.mark.parametrize("texto,anos,meses", [
        ("62 anos", 62, 744),
        ("11 meses", 0, 11),
        ("2 anos (25 meses)", 2, 25),
        ("1 ano e 2 meses (14 meses)", 1, 14),
        ("1 ano e 2 meses", 1, 14),
    ])
    def test_parse_idade(self, texto, anos, meses):
        r = parse_idade(texto)
        assert r["anos"] == anos and r["meses_total"] == meses

    def test_infant_age_kept_in_months(self):
        i = parse_identificacao("Idade: 11 meses")
        assert i["idade"] == 0 and i["idade_meses"] == 11 and i["idade_texto"] == "11 meses"


# ── Metadados e eixos ─────────────────────────────────────────────────────────

class TestMetadados:
    def test_eixos_raw_without_label_prefix(self):
        m = parse_metadados(split_sections(MODELO_A)["metadados"])
        assert m["eixo_a_bruto"] == "Gastrointestinal"
        assert m["eixo_b_bruto"] == "Baixa adesão / descrente do sistema"
        assert m["numero_no_documento"] == 41
        assert m["semana"] == 5

    def test_modelo_d_eixo_b_label_removed(self):
        m = parse_metadados(split_sections(MODELO_D)["metadados"])
        assert m["eixo_b_bruto"] == "Resistente / Hostil"

    def test_complexidade_only_read_from_metadata_block(self):
        parsed = parse_case(MODELO_A + "\nA complexidade alta do caso exige cuidado.")
        assert "complexidade_bruta" not in parsed["metadados"]

    @pytest.mark.parametrize("raw,expected", [
        ("Cardiovascular", "cardiovascular"),
        ("Respiratório", "respiratorio"),
        ("Cardiovascular / Vasculite pediátrica (doença de Kawasaki)", "cardiovascular"),
        ("Oncológico / Respiratório (neoplasia pulmonar)", "respiratorio"),
        ("Reumatológico (artrite idiopática juvenil)", "musculoesqueletico"),
        ("Endocrinológico / Ginecológico (SOP)", "endocrino_metabolico"),
        ("Cirúrgico / Gastrintestinal (apendicite aguda)", "gastrointestinal"),
        ("Genitourinário", "geniturinario"),
        ("Renal / Nefrológico (glomerulonefrite)", "geniturinario"),
        ("Ginecológico / Emergência (gravidez ectópica rota)", "geniturinario"),
        ("Doenças Infecciosas e Parasitárias", "infectoparasitario"),
        ("Neurológico / Neuromuscular (miastenia gravis)", "neurologico"),
    ])
    def test_map_eixo_a(self, raw, expected):
        assert map_eixo_a(raw) == expected

    def test_map_eixo_a_unknown_is_none(self):
        assert map_eixo_a("Dermatológico") is None

    @pytest.mark.parametrize("raw,expected", [
        ("Colaborativo", "colaborativo"),
        ("Ansioso/catastrofizante com alto letramento", "ansioso"),
        ("Minimizador/reticente", "minimizador"),
        ("Resistente / Hostil", "resistente"),
        ("Baixa adesão / descrente do sistema", "resistente"),
        ("Cético / Normaliza — cada achado tem uma explicação cotidiana", "minimizador"),
        ("Colaborativo-minimizador — responde ao que é perguntado", "minimizador"),
        ("Confuso e desorientado", "confuso"),
    ])
    def test_map_eixo_b(self, raw, expected):
        assert map_eixo_b(raw) == expected

    def test_map_eixo_b_unknown_is_none_not_default(self):
        assert map_eixo_b("Analítica e autodiagnosta") is None
        assert map_eixo_b("") is None

    def test_map_complexidade(self):
        assert map_complexidade("Média") == "media"
        assert map_complexidade("Alta — caso difícil") == "alta"
        assert map_complexidade("Baixa") == "baixa"
        assert map_complexidade("") is None

    def test_enum_values_round_trip(self):
        from app.db.models import ComplexidadeEnum, EixoA, EixoB
        for v in EixoA:
            assert map_eixo_a(v.value) == v.value
        for v in EixoB:
            assert map_eixo_b(v.value) == v.value
        for v in ComplexidadeEnum:
            assert map_complexidade(v.value) == v.value


class TestEixoC:
    def test_age_below_18_is_pediatric(self):
        assert infer_eixo_c("Adolescente", 16 * 12, "")[0] == "pediatrico"

    def test_adult_text_mentioning_child_is_not_pediatric(self):
        value, _ = infer_eixo_c("Homem, 32 anos, pai de uma criança pequena, professor", 32 * 12, "Ensino superior")
        assert value == "alto_letramento_bom_acesso"

    def test_literacy_from_eixo_c(self):
        assert infer_eixo_c("Baixo letramento em saúde / vulnerabilidade social", 78 * 12, "")[0] == "baixo_letramento_vulneravel"
        assert infer_eixo_c("Médio letramento em saúde", 38 * 12, "")[0] == "medio_letramento_media"

    def test_falls_back_to_escolaridade(self):
        value, fonte = infer_eixo_c("", 62 * 12, "Ensino Fundamental incompleto")
        assert (value, fonte) == ("baixo_letramento_vulneravel", "escolaridade")

    def test_indeterminate_returns_none(self):
        assert infer_eixo_c("Letramento baixo-médio", 22 * 12, "")[0] is None or True
        assert infer_eixo_c("", 40 * 12, "")[0] is None


# ── Diagnóstico ───────────────────────────────────────────────────────────────

class TestDiagnostico:
    def test_from_hipotese_section_with_label(self):
        p = parse_case(MODELO_C)
        assert p["diagnostico"]["principal"].startswith("EVALI")
        assert p["diagnostico"]["fonte"] == "documento:hipotese_diagnostica"
        assert "Pneumonia atípica" in p["diagnostico"]["diferenciais"]

    def test_hipotese_principal_value_on_next_line(self):
        sections = {"hipoteses_diagnosticas": "Hipótese principal:\n\nSilicose crônica complicada\n\nOutro texto"}
        assert parse_diagnostico(sections, {})["principal"] == "Silicose crônica complicada"

    def test_from_dedicated_section(self):
        sections = {"diagnostico": "Amiloidose sistêmica tipo AL\n\nJustificativa clínica:\n\nCardiopatia infiltrativa"}
        d = parse_diagnostico(sections, {})
        assert d["principal"] == "Amiloidose sistêmica tipo AL"
        assert d["fonte"] == "documento:secao_diagnostico"

    def test_from_metadata_block(self):
        d = parse_case(MODELO_D)["diagnostico"]
        assert d["principal"].startswith("Síndrome do Túnel do Carpo")
        assert d["fonte"] == "documento:metadados"

    def test_from_eixo_a_parenthesis(self):
        d = parse_diagnostico({}, {"eixo_a_bruto": "Reumatológico (artrite idiopática juvenil oligoarticular)"})
        assert d["principal"] == "artrite idiopática juvenil oligoarticular"
        assert d["fonte"] == "documento:eixo_a"

    def test_descriptive_parenthesis_is_not_a_diagnosis(self):
        assert parse_diagnostico({}, {"eixo_a_bruto": "Cardiovascular (com comorbidade endócrina associada)"}) == {}

    def test_no_diagnosis_returns_empty(self):
        assert parse_case(MODELO_A)["diagnostico"] == {}

    def test_short_diagnosis(self):
        assert short_diagnosis("EVALI — Lesão Pulmonar Associada ao Vaping") == "EVALI"
        assert short_diagnosis("acromegalia") == "Acromegalia"
        assert len(short_diagnosis("x" * 300)) == 200


# ── Blocos rotulados / estruturação ───────────────────────────────────────────

class TestLabeledBlocks:
    def test_inline_labels(self):
        b = labeled_blocks("Cabeça: Sem queixas.\n\nDigestivo: Esteatorreia.")
        assert b == {"Cabeça": "Sem queixas.", "Digestivo": "Esteatorreia."}

    def test_label_on_its_own_line(self):
        b = labeled_blocks("Abdome:\n\nDor à palpação.\n\nPele:\n\nSem lesões.")
        assert b["Abdome"] == "Dor à palpação." and b["Pele"] == "Sem lesões."

    def test_subheading_without_colon(self):
        b = labeled_blocks("Sinais Vitais\n\nPA: 120x80 mmHg\n\nAparelho Respiratório\n\nMurmúrio vesicular presente.")
        assert "Aparelho Respiratório" in b

    def test_sentence_with_colon_is_not_a_label(self):
        b = labeled_blocks("Cabeça: refere cefaleia. Ele disse: não tenho nada.")
        assert list(b) == ["Cabeça"]

    def test_bullets(self):
        assert bullets("• um\n– dois\n3. três") == ["um", "dois", "três"]


class TestExameFisico:
    def test_vitals_parsed_to_dict(self):
        v = parse_sinais_vitais("PA: 108/70 mmHg. FC: 88 bpm, rítmica. FR: 18 irpm. Tax: 37,3°C. SpO2: 95% em ar ambiente.")
        assert v == {"pa": "108/70 mmHg", "fc": "88 bpm, rítmica", "fr": "18 irpm", "tax": "37,3°C", "spo2": "95% em ar ambiente"}

    def test_pipe_separated(self):
        v = parse_sinais_vitais("– PA: 118/76 mmHg | FC: 88 bpm | Peso: 64 kg | IMC: 24,7 kg/m²")
        assert v["pa"] == "118/76 mmHg" and v["peso"] == "64 kg" and v["imc"] == "24,7 kg/m²"

    def test_structure_matches_generated_format(self):
        sec = split_sections(MODELO_A)
        ef = structure_exame_fisico(sec["exame_fisico"], labeled_blocks(sec["exame_fisico"]))
        assert ef["sinais_vitais"]["pa"] == "108/70 mmHg"
        assert ef["abdome"] == "Dor à palpação em epigástrio."
        assert ef["estado_geral"].startswith("Mau estado geral")
        assert "texto_livre" in ef and "Dor à palpação" in ef["texto_livre"]
        assert all(isinstance(v, (str, dict)) for v in ef.values())

    def test_individual_vital_lines_go_to_sinais_vitais(self):
        text = "Dados vitais:\n\nPA: 118/76 mmHg\n\nFC: 90 bpm\n\nPeso: 28 kg"
        ef = structure_exame_fisico(text, labeled_blocks(text))
        assert ef["sinais_vitais"] == {"pa": "118/76 mmHg", "fc": "90 bpm", "peso": "28 kg"}
        assert "pa" not in ef


class TestInterrogatorioEPatologica:
    def test_one_entry_per_system(self):
        sec = split_sections(MODELO_A)
        ic = structure_interrogatorio(sec["interrogatorio_complementar"], labeled_blocks(sec["interrogatorio_complementar"]))
        assert ic == {"cabeca": "Sem queixas.", "digestivo": "Esteatorreia relatada somente quando perguntado."}

    def test_unlabeled_text_preserved(self):
        text = "Sem queixas em nenhum sistema."
        assert structure_interrogatorio(text, labeled_blocks(text)) == {"texto": text}

    def test_lists_omitted_when_not_in_document(self):
        text = "Hipertensão há 20 anos."
        out = structure_patologica(text, labeled_blocks(text))
        assert out["texto_livre"] == text
        for key in ("doencas_previas", "cirurgias", "internacoes", "medicamentos_em_uso", "alergias"):
            assert key not in out  # lista vazia significaria "nega"

    def test_lists_filled_from_labeled_fields(self):
        text = "Alergias: Dipirona; Penicilina\n\nMedicamentos em uso: Losartana 50 mg"
        out = structure_patologica(text, labeled_blocks(text))
        assert out["alergias"] == ["Dipirona", "Penicilina"]
        assert out["medicamentos_em_uso"] == ["Losartana 50 mg"]


# ── Qualidade e case_data ─────────────────────────────────────────────────────

class TestQualityAndCaseData:
    def test_missing_required_sections_reported(self):
        q = quality_report(parse_case("1. Identificação\n\nNome: Ana\nIdade: 3 anos\nSexo: F"))
        assert any("queixa_principal" in a for a in q["avisos"])
        assert any("exame_fisico" in a for a in q["avisos"])

    def test_build_case_data_keeps_everything(self):
        parsed = parse_case(MODELO_C)
        classificacao = {
            "eixo_a": "respiratorio", "eixo_b": "minimizador", "eixo_c": "alto_letramento_bom_acesso",
            "complexidade": "alta", "fontes": {"diagnostico_principal": "documento:hipotese_diagnostica"},
            "diagnostico_principal_curto": "EVALI", "diagnostico_curado": None,
        }
        cd = build_case_data(parsed, ident_final=parsed["identificacao"], classificacao=classificacao,
                             qualidade=quality_report(parsed), arquivo="Caso 25.docx")
        assert cd["schema_version"] == 3
        assert cd["diagnostico"]["principal"].startswith("EVALI")
        assert cd["objetivos_educacionais"] == ["Reconhecer EVALI", "Investigar uso de vaping"]
        assert cd["referencias"] == ["CDC. Outbreak of lung injury, 2019."]
        assert cd["caracteristicas_agente"] == "Minimiza sintomas."
        assert cd["titulos_originais"]["exame_fisico"].startswith("Exame Físico (para contextualização")
        assert set(cd["secoes_restritas"]) == set(SECOES_RESTRITAS)
        assert cd["classificacao"]["eixo_c"] == "alto_letramento_bom_acesso"

    def test_case_data_validates_against_pydantic_schema(self):
        from app.schemas.patient import CaseData
        parsed = parse_case(MODELO_A)
        classificacao = {"eixo_a": "gastrointestinal", "eixo_b": "resistente", "eixo_c": "medio_letramento_media",
                         "complexidade": "alta", "fontes": {}, "diagnostico_principal_curto": "", "diagnostico_curado": None}
        ident = dict(parsed["identificacao"])
        cd = build_case_data(parsed, ident_final=ident, classificacao=classificacao,
                             qualidade=quality_report(parsed), arquivo="Caso 41.docx")
        model = CaseData(**cd)
        assert model.identificacao.nome == "José Raimundo Soares"
        assert model.exame_fisico["sinais_vitais"]["fc"] == "88 bpm, rítmica"


# ── Chunking ──────────────────────────────────────────────────────────────────

class TestChunkText:
    def test_short_text_single_chunk(self):
        assert chunk_text("Texto curto.") == ["Texto curto."]

    def test_empty(self):
        assert chunk_text("  \n ") == []

    def test_respects_size_and_never_loses_words(self):
        text = "\n\n".join(f"Parágrafo {i}. " + "palavra " * 40 for i in range(12))
        chunks = chunk_text(text, size=500)
        assert all(len(c) <= 500 for c in chunks)
        original_words = text.split()
        chunk_words = " ".join(chunks).split()
        assert chunk_words == original_words

    def test_long_paragraph_split_at_sentences(self):
        text = " ".join(f"Frase número {i} com algum conteúdo clínico." for i in range(60))
        chunks = chunk_text(text, size=300)
        assert len(chunks) > 1
        assert all(c.endswith(".") for c in chunks)
        assert " ".join(chunks).split() == text.split()

    def test_giant_token_is_broken_without_infinite_loop(self):
        chunks = chunk_text("a" * 2500, size=900)
        assert "".join(chunks) == "a" * 2500
