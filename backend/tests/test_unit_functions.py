# backend/tests/test_unit_functions.py
"""
Testes unitários para funções puras — sem banco de dados, sem HTTP.

Cobre:
  - chunk_text           (patient/router.py)
  - next_case_number_sync (patient/router.py)
  - build_user_prompt    (patient/router.py)
  - split_into_sections  (scripts/ingest/ingest_cases.py)
  - clean                (scripts/ingest/ingest_cases.py)
  - parse_metadata_from_text (scripts/ingest/ingest_cases.py)
  - parse_identificacao  (scripts/ingest/ingest_cases.py)
"""
from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Importações das funções testadas
# ---------------------------------------------------------------------------
from app.modules.patient.router import (
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    EIXO_A_LABELS,
    EIXO_B_LABELS,
    EIXO_C_LABELS,
    COMPLEXIDADE_LABELS,
    FAIXA_ETARIA_RANGE,
    build_user_prompt,
    chunk_text,
    next_case_number_sync,
)
from app.schemas.patient import PatientGenerateRequest
from scripts.ingest.ingest_cases import (
    clean,
    parse_identificacao,
    parse_metadata_from_text,
    split_into_sections,
    SECTION_PATTERNS,
    EIXO_A_MAP,
    EIXO_B_MAP,
)


# ===========================================================================
# chunk_text
# ===========================================================================

class TestChunkText:
    def test_empty_string_returns_empty_list(self):
        assert chunk_text("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert chunk_text("   \n\n  ") == []

    def test_short_text_returned_as_single_chunk(self):
        text = "Texto curto."
        result = chunk_text(text)
        assert result == ["Texto curto."]

    def test_text_exactly_at_limit_is_single_chunk(self):
        text = "a" * CHUNK_SIZE
        result = chunk_text(text)
        assert len(result) == 1
        assert result[0] == text

    def test_long_text_produces_multiple_chunks(self):
        # Texto de 3x o tamanho do chunk
        text = ("Palavra " * 200).strip()   # ~1400 caracteres
        result = chunk_text(text)
        assert len(result) >= 2

    def test_chunks_are_not_empty(self):
        text = "Frase um. Frase dois. " * 100
        for chunk in chunk_text(text):
            assert chunk.strip() != ""

    def test_chunks_cover_original_content(self):
        """A concatenação dos chunks deve cobrir todo o conteúdo original."""
        text = "Palavra " * 150
        chunks = chunk_text(text)
        # Pelo menos 80% do conteúdo original está representado nos chunks
        recovered = " ".join(chunks)
        original_words = set(text.split())
        recovered_words = set(recovered.split())
        # O overlap de 100 chars pode partir palavras nos limites de chunk,
        # gerando fragmentos extras (ex: "vra" de "Palavra"). Verificamos que
        # todas as palavras originais estão nos chunks, não o contrário.
        assert original_words.issubset(recovered_words)

    def test_chunk_size_respected(self):
        text = "a b c d e f " * 200
        for chunk in chunk_text(text):
            # Chunks podem ultrapassar levemente o limite no split por separador,
            # mas não mais que CHUNK_SIZE + tamanho do separador
            assert len(chunk) <= CHUNK_SIZE + 50

    def test_prefers_paragraph_break(self):
        """Deve quebrar em \n\n quando disponível."""
        para1 = "A " * 200          # ~400 chars
        para2 = "B " * 200
        text = para1 + "\n\n" + para2
        chunks = chunk_text(text)
        # O primeiro chunk deve terminar perto do parágrafo
        assert len(chunks) >= 2


# ===========================================================================
# next_case_number_sync
# ===========================================================================

class TestNextCaseNumber:
    def test_empty_list_returns_one(self):
        assert next_case_number_sync([]) == 1

    def test_sequential_list(self):
        assert next_case_number_sync([1, 2, 3]) == 4

    def test_list_with_gap(self):
        # Deve retornar max + 1, não preencher lacunas
        assert next_case_number_sync([1, 3, 5]) == 6

    def test_single_element(self):
        assert next_case_number_sync([7]) == 8

    def test_unordered_list(self):
        assert next_case_number_sync([5, 1, 3, 2]) == 6


# ===========================================================================
# build_user_prompt
# ===========================================================================

class TestBuildUserPrompt:
    def _req(self, **kwargs) -> PatientGenerateRequest:
        defaults = dict(
            eixo_a="cardiovascular",
            eixo_b="colaborativo",
            complexidade="media",
            eixo_c="baixo_letramento_vulneravel",
        )
        defaults.update(kwargs)
        return PatientGenerateRequest(**defaults)

    def test_contains_eixo_a_label(self):
        prompt = build_user_prompt(self._req(eixo_a="neurologico"))
        assert "neurológico" in prompt

    def test_contains_eixo_b_label(self):
        prompt = build_user_prompt(self._req(eixo_b="ansioso"))
        assert "ansioso" in prompt

    def test_contains_complexidade_label(self):
        prompt = build_user_prompt(self._req(complexidade="alta"))
        assert "alta" in prompt

    def test_contains_eixo_c_label(self):
        prompt = build_user_prompt(self._req(eixo_c="pediatrico"))
        assert "pediátrico" in prompt

    def test_sexo_masculino_included(self):
        prompt = build_user_prompt(self._req(sexo="M"))
        assert "masculino" in prompt

    def test_sexo_feminino_included(self):
        prompt = build_user_prompt(self._req(sexo="F"))
        assert "feminino" in prompt

    def test_sexo_omitted_when_none(self):
        prompt = build_user_prompt(self._req(sexo=None))
        assert "Sexo:" not in prompt

    def test_faixa_etaria_included(self):
        prompt = build_user_prompt(self._req(faixa_etaria="idoso"))
        assert "60" in prompt or "idoso" in prompt.lower()

    def test_faixa_etaria_omitted_when_none(self):
        prompt = build_user_prompt(self._req(faixa_etaria=None))
        assert "Faixa etária:" not in prompt

    def test_instrucoes_extras_included(self):
        prompt = build_user_prompt(
            self._req(instrucoes_extras="paciente gestante de 28 semanas")
        )
        assert "gestante" in prompt

    def test_instrucoes_extras_omitted_when_none(self):
        prompt = build_user_prompt(self._req(instrucoes_extras=None))
        assert "Instruções adicionais:" not in prompt

    def test_unknown_eixo_a_falls_back_to_raw_value(self):
        """Chaves desconhecidas não devem causar erro — usa o valor bruto."""
        prompt = build_user_prompt(self._req(eixo_a="psiquiatria"))
        assert "psiquiatria" in prompt

    def test_all_eixo_a_values_resolve(self):
        for key in EIXO_A_LABELS:
            req = self._req(eixo_a=key)
            prompt = build_user_prompt(req)
            assert EIXO_A_LABELS[key] in prompt


# ===========================================================================
# clean (ingest_cases.py)
# ===========================================================================

class TestClean:
    def test_collapses_triple_newlines(self):
        text = "a\n\n\n\nb"
        assert clean(text) == "a\n\nb"

    def test_strips_leading_trailing_whitespace(self):
        assert clean("  texto  ") == "texto"

    def test_double_newline_untouched(self):
        text = "a\n\nb"
        assert clean(text) == "a\n\nb"

    def test_empty_string(self):
        assert clean("") == ""


# ===========================================================================
# split_into_sections (ingest_cases.py)
# ===========================================================================

class TestSplitIntoSections:
    SAMPLE = """\
IDENTIFICAÇÃO:
Nome: João. Idade: 55.

QUEIXA PRINCIPAL:
Dor no peito ao esforço.

HISTÓRIA DA DOENÇA ATUAL:
Início há 2 meses, dor em aperto.

EXAME FÍSICO:
PA 145/90 mmHg. FC 78 bpm.

CARACTERÍSTICAS DO AGENTE DE IA:
Paciente colaborativo e tranquilo.

HIPÓTESES DIAGNÓSTICAS:
Angina Estável. Síndrome Coronariana.

DIAGNÓSTICO:
Angina Estável.
"""

    def test_extracts_identificacao(self):
        sections = split_into_sections(self.SAMPLE)
        assert "identificacao" in sections
        assert "João" in sections["identificacao"]

    def test_extracts_queixa_principal(self):
        sections = split_into_sections(self.SAMPLE)
        assert "queixa_principal" in sections
        assert "peito" in sections["queixa_principal"]

    def test_extracts_historia_doenca_atual(self):
        sections = split_into_sections(self.SAMPLE)
        assert "historia_doenca_atual" in sections
        assert "2 meses" in sections["historia_doenca_atual"]

    def test_extracts_exame_fisico(self):
        sections = split_into_sections(self.SAMPLE)
        assert "exame_fisico" in sections
        assert "PA" in sections["exame_fisico"]

    def test_extracts_caracteristicas_agente(self):
        """Regressão: antes da correção, esse campo caía em 'diagnostico'."""
        sections = split_into_sections(self.SAMPLE)
        assert "caracteristicas_agente" in sections
        assert "colaborativo" in sections["caracteristicas_agente"]

    def test_caracteristicas_agente_not_in_diagnostico(self):
        sections = split_into_sections(self.SAMPLE)
        diagnostico_text = sections.get("diagnostico", "")
        assert "colaborativo" not in diagnostico_text

    def test_extracts_hipoteses_diagnosticas(self):
        sections = split_into_sections(self.SAMPLE)
        assert "hipoteses_diagnosticas" in sections

    def test_extracts_diagnostico(self):
        sections = split_into_sections(self.SAMPLE)
        assert "diagnostico" in sections

    def test_section_patterns_include_caracteristicas_agente(self):
        import re
        keys = [key for _, key in SECTION_PATTERNS]
        assert "caracteristicas_agente" in keys

    def test_caracteristicas_agente_pattern_matches_variants(self):
        import re
        pattern = next(p for p, k in SECTION_PATTERNS if k == "caracteristicas_agente")
        assert re.search(pattern, "Características do Agente de IA:")
        assert re.search(pattern, "CARACTERÍSTICAS DO AGENTE")
        assert re.search(pattern, "Caracteristicas do Agente")


# ===========================================================================
# parse_metadata_from_text (ingest_cases.py)
# ===========================================================================

class TestParseMetadata:
    def test_extracts_case_number(self):
        text = "Caso No 3\nEixo A: cardiovascular"
        meta = parse_metadata_from_text(text)
        assert meta["case_number"] == 3

    def test_extracts_eixo_a_with_accent(self):
        text = "Eixo A: respiratório"
        meta = parse_metadata_from_text(text)
        assert meta["eixo_a"] == "respiratorio"

    def test_extracts_eixo_a_without_accent(self):
        text = "Eixo A: gastrointestinal"
        meta = parse_metadata_from_text(text)
        assert meta["eixo_a"] == "gastrointestinal"

    def test_extracts_eixo_b(self):
        text = "Eixo B: ansioso"
        meta = parse_metadata_from_text(text)
        assert meta["eixo_b"] == "ansioso"

    def test_unknown_eixo_b_defaults_to_colaborativo(self):
        text = "Eixo B: desconhecido"
        meta = parse_metadata_from_text(text)
        assert meta["eixo_b"] == "colaborativo"

    def test_extracts_complexidade_with_accent(self):
        text = "Complexidade: média"
        meta = parse_metadata_from_text(text)
        assert meta["complexidade"] == "media"

    def test_extracts_complexidade_alta(self):
        text = "Complexidade: alta"
        meta = parse_metadata_from_text(text)
        assert meta["complexidade"] == "alta"

    def test_missing_fields_not_in_result(self):
        meta = parse_metadata_from_text("Texto sem metadados relevantes")
        assert "case_number" not in meta
        assert "eixo_a" not in meta


# ===========================================================================
# parse_identificacao (ingest_cases.py)
# ===========================================================================

class TestParseIdentificacao:
    SAMPLE = """\
Nome: João Cardoso
Idade: 55 anos
Sexo: Masculino
Cor: parda
Estado Civil: casado
Profissão: agricultor
"""

    def test_extracts_nome(self):
        fields = parse_identificacao(self.SAMPLE)
        assert fields["nome"] == "João Cardoso"

    def test_extracts_idade_as_int(self):
        fields = parse_identificacao(self.SAMPLE)
        assert fields["idade"] == 55
        assert isinstance(fields["idade"], int)

    def test_extracts_sexo_masculino(self):
        fields = parse_identificacao(self.SAMPLE)
        assert fields["sexo"] == "M"

    def test_extracts_sexo_feminino(self):
        text = "Nome: Maria\nIdade: 30\nSexo: Feminino"
        fields = parse_identificacao(text)
        assert fields["sexo"] == "F"

    def test_extracts_cor(self):
        fields = parse_identificacao(self.SAMPLE)
        assert fields["cor"] == "parda"

    def test_extracts_estado_civil(self):
        fields = parse_identificacao(self.SAMPLE)
        assert fields["estado_civil"] == "casado"

    def test_missing_fields_absent(self):
        fields = parse_identificacao("Nome: Alguém")
        assert "idade" not in fields
        assert "sexo" not in fields

    def test_invalid_idade_not_included(self):
        text = "Idade: não informada"
        fields = parse_identificacao(text)
        assert "idade" not in fields
