# backend/app/schemas/patient.py
from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class Identificacao(BaseModel):
    nome: str
    idade: int
    sexo: str
    cor: Optional[str] = None
    estado_civil: Optional[str] = None
    profissao: Optional[str] = None
    religiao: Optional[str] = None
    residencia: Optional[str] = None
    naturalidade: Optional[str] = None


class HistoriaFisiologica(BaseModel):
    texto_livre: Optional[str] = None


class HistoriaPatologica(BaseModel):
    doencas_previas: list[str] = Field(default_factory=list)
    cirurgias: list[str] = Field(default_factory=list)
    internacoes: list[str] = Field(default_factory=list)
    medicamentos_em_uso: list[str] = Field(default_factory=list)
    alergias: list[str] = Field(default_factory=list)
    texto_livre: Optional[str] = None


class HistoriaFamiliar(BaseModel):
    texto_livre: Optional[str] = None


class HistoriaSocial(BaseModel):
    tabagismo: Optional[str] = None
    etilismo: Optional[str] = None
    texto_livre: Optional[str] = None


class ExameFisico(BaseModel):
    estado_geral: Optional[str] = None
    texto_livre: Optional[str] = None


class CaseData(BaseModel):
    identificacao: Identificacao
    queixa_principal_texto: str
    historia_doenca_atual: str
    interrogatorio_complementar: Optional[dict] = Field(default_factory=dict)
    historia_fisiologica: Optional[HistoriaFisiologica] = None
    historia_patologica: Optional[HistoriaPatologica] = None
    historia_familiar: Optional[HistoriaFamiliar] = None
    historia_social: Optional[HistoriaSocial] = None
    exame_fisico: Optional[ExameFisico] = None
    diagnostico_completo: Optional[str] = None
    hipoteses_diagnosticas: list[str] = Field(default_factory=list)
    raw_sections: dict[str, str] = Field(default_factory=dict)


class VirtualPatientCreate(BaseModel):
    case_number: int
    eixo_a: str
    eixo_b: str
    eixo_c: str
    complexidade: str
    nome: str
    idade: int
    sexo: str
    queixa_principal: str
    diagnostico_principal: str
    case_data: CaseData


class VirtualPatientResponse(BaseModel):
    id: UUID
    case_number: int
    eixo_a: str
    eixo_b: str
    eixo_c: str
    complexidade: str
    nome: str
    idade: int
    sexo: str
    queixa_principal: str
    diagnostico_principal: str
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class VirtualPatientDetail(VirtualPatientResponse):
    case_data: dict
    model_config = {"from_attributes": True}


class KnowledgeSearchRequest(BaseModel):
    query: str
    patient_id: Optional[UUID] = None
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchResult(BaseModel):
    patient_id: UUID
    patient_name: str
    section: str
    content: str
    similarity: float


# ── Geração de pacientes via LLM ──────────────────────────────────────────────

class PatientGenerateRequest(BaseModel):
    eixo_a: str = Field(
        description=(
            "Área clínica principal. Valores: cardiovascular, respiratorio, "
            "gastrointestinal, neurologico, musculoesqueletico, "
            "endocrino_metabolico, geniturinario"
        )
    )
    eixo_b: str = Field(
        default="colaborativo",
        description="Perfil comportamental. Valores: colaborativo, ansioso, resistente, confuso, minimizador",
    )
    complexidade: str = Field(
        default="media",
        description="Complexidade do caso. Valores: baixa, media, alta",
    )
    eixo_c: str = Field(
        default="baixo_letramento_vulneravel",
        description="Perfil socioeconômico. Valores: baixo_letramento_vulneravel, medio_letramento_media, alto_letramento_bom_acesso, pediatrico",
    )
    sexo: Optional[str] = Field(
        default=None,
        description="M ou F. Se omitido, o LLM escolhe coerentemente com o caso.",
    )
    faixa_etaria: Optional[str] = Field(
        default=None,
        description="Faixa etária: crianca (0-12), adolescente (13-17), adulto (18-59), idoso (60+). Se omitido, o LLM escolhe.",
    )
    instrucoes_extras: Optional[str] = Field(
        default=None,
        description="Instruções livres para personalizar o caso gerado (ex: 'paciente gestante', 'contexto rural').",
    )


class PatientGenerateResponse(BaseModel):
    patient: VirtualPatientDetail
    chunks_ingested: int
    generated_by: str = "gpt-4o"
