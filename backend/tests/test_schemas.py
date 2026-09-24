# backend/tests/test_schemas.py
"""
Testes de schemas Pydantic e consistência de enums.

Verifica:
  - Validação e defaults de PatientGenerateRequest
  - PatientGenerateResponse aninha VirtualPatientDetail (com case_data)
  - Todos os valores de EixoA/B/C e Complexidade têm label correspondente
  - EIXO_A_MAP no ingest cobre todos os valores de EixoA
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.db.models import EixoA, EixoB, EixoC, ComplexidadeEnum
from app.modules.patient.router import (
    EIXO_A_LABELS,
    EIXO_B_LABELS,
    EIXO_C_LABELS,
    COMPLEXIDADE_LABELS,
)
from app.schemas.patient import (
    PatientGenerateRequest,
    PatientGenerateResponse,
    VirtualPatientDetail,
    VirtualPatientResponse,
)
from scripts.ingest.ingest_cases import EIXO_A_MAP, EIXO_B_MAP, COMPLEXIDADE_MAP


# ===========================================================================
# PatientGenerateRequest — validação
# ===========================================================================

class TestPatientGenerateRequest:
    def test_minimal_request_requires_only_eixo_a(self):
        req = PatientGenerateRequest(eixo_a="cardiovascular")
        assert req.eixo_a == "cardiovascular"

    def test_default_eixo_b_is_colaborativo(self):
        req = PatientGenerateRequest(eixo_a="neurologico")
        assert req.eixo_b == "colaborativo"

    def test_default_complexidade_is_media(self):
        req = PatientGenerateRequest(eixo_a="neurologico")
        assert req.complexidade == "media"

    def test_default_eixo_c(self):
        req = PatientGenerateRequest(eixo_a="neurologico")
        assert req.eixo_c == "baixo_letramento_vulneravel"

    def test_default_sexo_is_none(self):
        req = PatientGenerateRequest(eixo_a="neurologico")
        assert req.sexo is None

    def test_default_faixa_etaria_is_none(self):
        req = PatientGenerateRequest(eixo_a="neurologico")
        assert req.faixa_etaria is None

    def test_default_instrucoes_extras_is_none(self):
        req = PatientGenerateRequest(eixo_a="neurologico")
        assert req.instrucoes_extras is None

    def test_missing_eixo_a_raises_validation_error(self):
        with pytest.raises(ValidationError):
            PatientGenerateRequest()  # type: ignore[call-arg]

    def test_all_fields_set(self):
        req = PatientGenerateRequest(
            eixo_a="respiratorio",
            eixo_b="ansioso",
            complexidade="alta",
            eixo_c="pediatrico",
            sexo="F",
            faixa_etaria="crianca",
            instrucoes_extras="paciente com asma persistente",
        )
        assert req.eixo_a == "respiratorio"
        assert req.eixo_b == "ansioso"
        assert req.complexidade == "alta"
        assert req.eixo_c == "pediatrico"
        assert req.sexo == "F"
        assert req.faixa_etaria == "crianca"
        assert req.instrucoes_extras == "paciente com asma persistente"


# ===========================================================================
# PatientGenerateResponse — deve incluir case_data via VirtualPatientDetail
# ===========================================================================

class TestPatientGenerateResponseSchema:
    def test_patient_field_is_virtual_patient_detail(self):
        """PatientGenerateResponse.patient deve ser VirtualPatientDetail, não VirtualPatientResponse."""
        import typing
        # from __future__ import annotations faz __annotations__ retornar strings;
        # get_type_hints() resolve as strings para os tipos reais.
        hints = typing.get_type_hints(PatientGenerateResponse)
        field_type = hints.get("patient")
        assert field_type is VirtualPatientDetail, (
            f"PatientGenerateResponse.patient deve ser VirtualPatientDetail, "
            f"mas é {field_type}. Isso causa ausência do case_data na resposta."
        )

    def test_virtual_patient_detail_has_case_data(self):
        assert "case_data" in VirtualPatientDetail.__annotations__

    def test_virtual_patient_response_has_no_case_data(self):
        assert "case_data" not in VirtualPatientResponse.__annotations__

    def test_generate_response_has_chunks_ingested(self):
        assert "chunks_ingested" in PatientGenerateResponse.__annotations__

    def test_generate_response_has_generated_by(self):
        assert "generated_by" in PatientGenerateResponse.__annotations__


# ===========================================================================
# Consistência de enums — labels e mapeamentos
# ===========================================================================

class TestEnumConsistency:
    def test_all_eixo_a_values_have_label(self):
        for value in EixoA:
            assert value.value in EIXO_A_LABELS, (
                f"EixoA.{value.name} ({value.value!r}) não tem label em EIXO_A_LABELS"
            )

    def test_all_eixo_b_values_have_label(self):
        for value in EixoB:
            assert value.value in EIXO_B_LABELS, (
                f"EixoB.{value.name} ({value.value!r}) não tem label em EIXO_B_LABELS"
            )

    def test_all_eixo_c_values_have_label(self):
        for value in EixoC:
            assert value.value in EIXO_C_LABELS, (
                f"EixoC.{value.name} ({value.value!r}) não tem label em EIXO_C_LABELS"
            )

    def test_all_complexidade_values_have_label(self):
        for value in ComplexidadeEnum:
            assert value.value in COMPLEXIDADE_LABELS, (
                f"ComplexidadeEnum.{value.name} ({value.value!r}) não tem label"
            )

    def test_eixo_a_map_covers_all_enum_values(self):
        """Todos os valores do enum EixoA devem ser reconhecidos pelo EIXO_A_MAP do ingest."""
        for value in EixoA:
            assert value.value in EIXO_A_MAP, (
                f"EixoA.{value.name} ({value.value!r}) não está mapeado em EIXO_A_MAP"
            )

    def test_eixo_b_map_covers_all_enum_values(self):
        for value in EixoB:
            assert value.value in EIXO_B_MAP, (
                f"EixoB.{value.name} ({value.value!r}) não está mapeado em EIXO_B_MAP"
            )

    def test_complexidade_map_covers_all_enum_values(self):
        for value in ComplexidadeEnum:
            assert value.value in COMPLEXIDADE_MAP, (
                f"ComplexidadeEnum.{value.name} não está em COMPLEXIDADE_MAP"
            )

    def test_no_taciturno_in_eixo_b(self):
        """Regressão: 'taciturno' foi removido do enum EixoB."""
        values = [v.value for v in EixoB]
        assert "taciturno" not in values

    def test_eixo_b_has_confuso(self):
        assert any(v.value == "confuso" for v in EixoB)

    def test_eixo_b_has_minimizador(self):
        assert any(v.value == "minimizador" for v in EixoB)

    def test_eixo_a_has_no_specialty_names(self):
        """Regressão: o frontend usava 'cardiologia', 'neurologia' — devem ser os valores do enum."""
        wrong_values = {"cardiologia", "neurologia", "endocrinologia", "gastroenterologia", "psiquiatria"}
        enum_values = {v.value for v in EixoA}
        overlap = wrong_values & enum_values
        assert overlap == set(), f"Valores de especialidade incorretos no EixoA: {overlap}"

    def test_eixo_a_expected_values(self):
        expected = {
            "cardiovascular", "respiratorio", "gastrointestinal",
            "neurologico", "musculoesqueletico", "endocrino_metabolico", "geniturinario",
        }
        actual = {v.value for v in EixoA}
        assert actual == expected


# ===========================================================================
# sys.path ordering no ingest_cases.py
# ===========================================================================

class TestIngestSysPath:
    def test_sys_path_insert_before_app_import(self):
        """
        Regressão Bug 6: sys.path.insert deve aparecer antes de 'from app.db.models'.
        Verifica no código-fonte que a ordem está correta.
        """
        import ast
        from pathlib import Path

        src_path = Path(__file__).parent.parent / "scripts" / "ingest" / "ingest_cases.py"
        source = src_path.read_text()

        sys_path_line = next(
            (i for i, line in enumerate(source.splitlines()) if "sys.path.insert" in line),
            None,
        )
        app_import_line = next(
            (i for i, line in enumerate(source.splitlines()) if "from app.db.models import" in line),
            None,
        )
        assert sys_path_line is not None, "sys.path.insert não encontrado em ingest_cases.py"
        assert app_import_line is not None, "from app.db.models não encontrado em ingest_cases.py"
        assert sys_path_line < app_import_line, (
            f"sys.path.insert (linha {sys_path_line + 1}) deve vir ANTES de "
            f"from app.db.models (linha {app_import_line + 1})"
        )

    def test_no_duplicate_ingestion_complete_log(self):
        """Regressão Bug 9: log 'Ingestion complete' não deve aparecer duplicado."""
        from pathlib import Path

        src_path = Path(__file__).parent.parent / "scripts" / "ingest" / "ingest_cases.py"
        source = src_path.read_text()
        occurrences = source.count('"Ingestion complete"')
        assert occurrences <= 1, (
            f"'Ingestion complete' aparece {occurrences} vezes — esperado no máximo 1"
        )
