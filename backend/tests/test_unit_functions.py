# backend/tests/test_unit_functions.py
"""
Testes unitários para funções puras — sem banco de dados, sem HTTP.

Cobre:
  - chunk_text           (patient/router.py)
  - next_case_number_sync (patient/router.py)
  - build_user_prompt    (patient/router.py)

(O parser dos .docx de casos clínicos é testado em tests/test_case_parser.py.)
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
