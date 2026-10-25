# backend/app/schemas/patient.py
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional, Union
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
    # Modelo padronizado (seção 1 completa)
    nacionalidade: Optional[str] = None
    profissao_anterior: Optional[str] = None
    ocupacao: Optional[str] = None
    escolaridade: Optional[str] = None
    residencias_anteriores: Optional[str] = None
    informante: Optional[str] = None


class HistoriaFisiologica(BaseModel):
    texto_livre: Optional[str] = None


class HistoriaPatologica(BaseModel):
    doencas_previas: list[str] = Field(default_factory=list)
    cirurgias: list[str] = Field(default_factory=list)
    internacoes: list[str] = Field(default_factory=list)
    medicamentos_em_uso: list[str] = Field(default_factory=list)
    alergias: list[str] = Field(default_factory=list)
    texto_livre: Optional[str] = None
    medicacoes_observacao: Optional[str] = None  # "Observação:" da seção 6 (Medicações em Uso)


class HistoriaFamiliar(BaseModel):
    texto_livre: Optional[str] = None


class HistoriaSocial(BaseModel):
    tabagismo: Optional[str] = None
    etilismo: Optional[str] = None
    texto_livre: Optional[str] = None


class CaseData(BaseModel):
    identificacao: Identificacao
    queixa_principal_texto: str
    historia_doenca_atual: str
    # Uma entrada por sistema (ex: {"cabeca": "...", "aparelho_respiratorio_circulatorio": "..."}).
    # Aceita também o formato antigo {"texto": "..."} para retrocompatibilidade.
    interrogatorio_complementar: Optional[dict[str, str]] = Field(default_factory=dict)
    historia_fisiologica: Optional[HistoriaFisiologica] = None
    historia_patologica: Optional[HistoriaPatologica] = None
    historia_familiar: Optional[HistoriaFamiliar] = None
    historia_social: Optional[HistoriaSocial] = None
    # Aceita o formato estruturado novo (sinais_vitais + achados por aparelho)
    # e o formato antigo ({"estado_geral": ..., "texto_livre": ...}), daí o dict genérico.
    exame_fisico: Optional[dict] = None
    diagnostico_completo: Optional[str] = None
    hipoteses_diagnosticas: list[str] = Field(default_factory=list)
    caracteristicas_agente: Optional[str] = None
    # Modelo padronizado: texto "Contexto para o aluno" e agente estruturado
    # {perfil: texto, voz_postura_discurso: [..], vocabulario: [..], reacoes_emocionais: [..], ...}
    contexto_aluno: Optional[str] = None
    agente_ia: Optional[dict[str, Any]] = None
    raw_sections: dict[str, str] = Field(default_factory=dict)
    # ── Campos gravados pelo pipeline de ingestão (scripts/ingest, schema_version 2) ──
    schema_version: Optional[int] = None
    arquivo_origem: Optional[str] = None
    antecedentes_gineco_obstetricos: Optional[dict] = None
    observacoes_especificas: Optional[str] = None
    exames_complementares: Optional[str] = None
    # {principal, fonte, diferenciais, justificativa, hipoteses, ...} — conteúdo do facilitador
    diagnostico: Optional[dict] = None
    objetivos_educacionais: list[str] = Field(default_factory=list)
    referencias: list[str] = Field(default_factory=list)
    contexto_facilitador: Optional[str] = None
    # Seções que não podem ser reveladas ao estudante / usadas como fala do paciente.
    secoes_restritas: list[str] = Field(default_factory=list)
    metadados: Optional[dict] = None
    # {eixo_a, eixo_b, eixo_c, complexidade, fontes: {campo: origem}}
    classificacao: Optional[dict] = None
    # {avisos, divergencias, secoes_encontradas, revisao_necessaria}
    qualidade: Optional[dict] = None
    titulos_originais: dict[str, str] = Field(default_factory=dict)


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
    condicao_social: Optional[str] = Field(
        default=None,
        pattern="^(baixa|media|alta)$",
        description="Condição social (modelo padronizado, Eixo C): baixa, media ou alta. Se omitida, o LLM deduz do Eixo C.",
    )
    instrucoes_extras: Optional[str] = Field(
        default=None,
        description="Instruções livres para personalizar o caso gerado (ex: 'paciente gestante', 'contexto rural').",
    )


class PatientGenerateResponse(BaseModel):
    patient: VirtualPatientDetail
    chunks_ingested: int
    generated_by: str = "gpt-4o"


# ── Cadastro manual / importação de DOCX ──────────────────────────────────────

class PatientManualRequest(BaseModel):
    """Cadastro manual — sem fallbacks; campos obrigatórios validados."""
    # Classificação clínica
    eixo_a: str = Field(min_length=1)
    eixo_b: str = "colaborativo"
    eixo_c: str = "baixo_letramento_vulneravel"
    complexidade: str = "media"
    # Detalhes do perfil no modelo padronizado (o enum eixo_c não os distingue)
    letramento: Optional[str] = Field(default=None, pattern="^(baixo|medio|alto)$")
    condicao_social: Optional[str] = Field(default=None, pattern="^(baixa|media|alta)$")
    nuance_eixo_b: Optional[str] = None

    # Identificação — obrigatórios
    nome: str = Field(min_length=2, max_length=200)
    idade: int = Field(ge=0, le=130)
    sexo: str = Field(pattern="^[MF]$")
    queixa_principal: str = Field(min_length=5)
    diagnostico_principal: str = Field(min_length=3)

    # Identificação — opcionais
    cor: Optional[str] = None
    estado_civil: Optional[str] = None
    profissao: Optional[str] = None
    religiao: Optional[str] = None
    residencia: Optional[str] = None
    naturalidade: Optional[str] = None
    nacionalidade: Optional[str] = None
    profissao_anterior: Optional[str] = None
    ocupacao: Optional[str] = None
    escolaridade: Optional[str] = None
    residencias_anteriores: Optional[str] = None
    informante: Optional[str] = None

    # Seções narrativas
    contexto_aluno: Optional[str] = None
    historia_doenca_atual: str = Field(min_length=50, description="Mínimo 50 caracteres")
    # Um texto por sistema ({"cabeca": "...", ...}); texto único continua aceito (formato antigo).
    interrogatorio_complementar: Optional[Union[dict[str, str], str]] = None
    historia_fisiologica: Optional[str] = None
    historia_familiar: Optional[str] = None
    # {"sinais_vitais": {"pa": ...}, "exame_fisico_geral": "...", "aparelho_cardiovascular": "...", ...}
    # ou texto único (formato antigo).
    exame_fisico: Optional[Union[dict[str, Any], str]] = None
    # {"perfil": "...", "voz_postura_discurso": ["..."], ...}; `caracteristicas_agente` (texto) é o formato antigo.
    agente_ia: Optional[dict[str, Any]] = None
    caracteristicas_agente: Optional[str] = None

    # História patológica
    doencas_previas: list[str] = Field(default_factory=list)
    cirurgias: list[str] = Field(default_factory=list)
    internacoes: list[str] = Field(default_factory=list)
    medicamentos_em_uso: list[str] = Field(default_factory=list)
    alergias: list[str] = Field(default_factory=list)
    historia_patologica_texto: Optional[str] = None
    medicacoes_observacao: Optional[str] = None

    # História social (seção 8 do modelo: "Hábitos de vida")
    tabagismo: Optional[str] = None
    etilismo: Optional[str] = None
    historia_social_texto: Optional[str] = None

    # Hipóteses
    hipoteses_diagnosticas: list[str] = Field(default_factory=list)


class DocxValidationIssue(BaseModel):
    field: str      # ex: "historia_doenca_atual"
    severity: str   # "error" | "warning"
    message: str


class DocxParseResponse(BaseModel):
    extracted: dict  # mesmo shape do PatientManualRequest
    issues: list[DocxValidationIssue]
    can_save: bool   # True se não há erros (só warnings)
