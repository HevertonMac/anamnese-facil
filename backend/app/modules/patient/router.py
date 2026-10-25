# backend/app/modules/patient/router.py
"""
Módulo de cadastro de pacientes virtuais.

Os três caminhos de entrada produzem o mesmo `case_data` (modelo padronizado, ver `case_template.py`):
  POST /api/v1/patients/generate    — gera o caso via GPT-4o
  POST /api/v1/patients/manual      — cadastro manual (formulário)
  POST /api/v1/patients/parse-docx  — extrai um DOCX no formato do formulário (não grava)

Gravação: paciente → chunks por seção → embeddings → PostgreSQL.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import KnowledgeChunk, VirtualPatient
from app.modules.patient.case_template import (
    AGENTE_SECOES, SISTEMAS, build_chunk_sections, build_identificacao,
    normalize_agente, normalize_exame_fisico, normalize_interrogatorio,
)
from app.schemas.patient import (
    DocxParseResponse, DocxValidationIssue, PatientGenerateRequest, PatientGenerateResponse,
    PatientManualRequest, VirtualPatientDetail,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/patients", tags=["patients"])

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
EMBEDDING_DIM = 1536
EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
SCHEMA_VERSION = 3

EIXO_A_LABELS = {
    "cardiovascular": "cardiovascular",
    "respiratorio": "respiratório",
    "gastrointestinal": "gastrointestinal",
    "neurologico": "neurológico",
    "musculoesqueletico": "musculoesquelético",
    "endocrino_metabolico": "endócrino/metabólico",
    "geniturinario": "geniturinário",
    "infectoparasitario": "infectoparasitário",
}

EIXO_B_LABELS = {
    "colaborativo": "colaborativo e comunicativo",
    "ansioso": "ansioso e hipervigilante",
    "resistente": "resistente e desconfiado",
    "confuso": "confuso e com dificuldade para relatar",
    "minimizador": "minimizador dos sintomas",
}

EIXO_C_LABELS = {
    "baixo_letramento_vulneravel": "baixo letramento em saúde, contexto socioeconômico vulnerável, linguagem simples, dificuldade em descrever sintomas com precisão",
    "medio_letramento_media": "letramento médio, classe média, compreende orientações básicas, alguma familiaridade com serviços de saúde",
    "alto_letramento_bom_acesso": "alto letramento em saúde, bom acesso a serviços, pode usar termos técnicos, questionador e informado",
    "pediatrico": "paciente pediátrico — respostas dadas pelo responsável, linguagem adaptada à idade da criança",
}

COMPLEXIDADE_LABELS = {
    "baixa": "baixa (quadro clínico simples, diagnóstico direto)",
    "media": "média (dois ou mais diagnósticos diferenciais plausíveis)",
    "alta": "alta (múltiplas comorbidades, apresentação atípica ou contexto social desfavorável)",
}

CONDICAO_SOCIAL_LABELS = {
    "baixa": "baixa (renda instável, dependente do SUS, moradia/saneamento precários)",
    "media": "média (renda estável, moradia adequada, rede pública ou plano básico)",
    "alta": "alta (boa renda, plano de saúde privado, moradia própria em bairro nobre)",
}

FAIXA_ETARIA_RANGE = {
    "crianca": "entre 3 e 12 anos",
    "adolescente": "entre 13 e 17 anos",
    "adulto": "entre 18 e 59 anos",
    "idoso": "entre 60 e 85 anos",
}

_SISTEMAS_JSON = ",\n".join(
    f'    "{key}": "o que nega ou confirma quando perguntado sobre: {label.lower()}"' for key, label in SISTEMAS
)

GENERATION_SYSTEM_PROMPT = f"""\
Você é um especialista em semiologia médica e educação médica da UFPI.
Sua tarefa é criar um caso clínico sintético, realista e educacionalmente rico
para treinamento de anamnese por estudantes de medicina, seguindo o MODELO PADRONIZADO
de casos do VipLab UFPI (identificação completa, interrogatório por sistema, medicações em uso,
exame físico por aparelho e roteiro de comportamento do paciente virtual).

O caso deve:
- Ser clinicamente coerente e compatível com a prática médica brasileira
- Usar linguagem coloquial para as falas do paciente (sem jargão técnico)
- Incluir detalhes sociais, culturais e emocionais que tornem o personagem verossímil
- Conter informações suficientes para uma anamnese completa de 20-30 min
- NÃO revelar o diagnóstico ao paciente nem ao aluno — o paciente não sabe o diagnóstico
- Ser coerente com os Eixos B (comunicação), C (letramento/condição social) e a complexidade pedidos

Retorne APENAS um objeto JSON válido com exatamente esta estrutura (sem markdown, sem explicações):

{{
  "nome": "Nome completo brasileiro",
  "idade": 45,
  "sexo": "M" ou "F",
  "queixa_principal": "frase curta exatamente como o paciente diria, entre aspas",
  "diagnostico_principal": "diagnóstico correto para o professor (curto)",
  "contexto_aluno": "1-2 parágrafos de cena: consultório, quem acompanha o paciente, como ele chega, clima da consulta (sem revelar diagnóstico)",
  "identificacao": {{
    "cor": "parda/branca/preta/amarela/indígena",
    "estado_civil": "casado/solteiro/viúvo/divorciado",
    "nacionalidade": "Brasileira",
    "naturalidade": "cidade – UF",
    "profissao": "profissão atual realista",
    "profissao_anterior": "profissão anterior ou 'Não se aplica'",
    "ocupacao": "ocupação atual",
    "escolaridade": "escolaridade coerente com o Eixo C",
    "religiao": "religião",
    "residencia": "bairro/cidade piauiense ou nordestina, tempo de moradia, com quem mora",
    "residencias_anteriores": "ou 'Não se aplica'",
    "informante": "apenas se o paciente não for o informante (criança, idoso confuso): quem é e como participa; senão omita"
  }},
  "historia_doenca_atual": "narrativa detalhada em terceira pessoa (400-600 palavras). Inclua: início, duração, evolução, fatores de melhora/piora, sintomas associados, medicamentos em uso se relevante, comportamento do paciente frente à doença",
  "interrogatorio_complementar": {{
{_SISTEMAS_JSON}
  }},
  "historia_fisiologica": "antecedentes fisiológicos: nascimento, desenvolvimento, puberdade, gestações/partos, menopausa se aplicável",
  "historia_patologica": {{
    "doencas_previas": ["lista de doenças pregressas"],
    "cirurgias": ["lista ou 'nega cirurgias'"],
    "internacoes": ["lista ou 'nega internações'"],
    "medicamentos_em_uso": ["Nome dose — posologia (finalidade). Ex: Losartana 50 mg — 1 comprimido/dia (tratamento da hipertensão arterial)"],
    "medicacoes_observacao": "como o paciente realmente toma/entende os remédios (adesão, automedicação, o que só revela se perguntado)",
    "alergias": ["lista ou 'nega alergias'"],
    "texto_livre": "antecedentes patológicos em prosa: vacinas, doenças da infância, comorbidades, internações"
  }},
  "historia_familiar": "saúde detalhada dos pais (causa e idade do óbito se falecidos), irmãos, filhos — doenças prevalentes",
  "historia_social": {{
    "tabagismo": "ex-tabagista X maços-ano / tabagista X cigarros/dia há Y anos / nega tabagismo",
    "etilismo": "descrição quantificada do uso de álcool",
    "texto_livre": "hábitos de vida: moradia, saneamento, renda, com quem mora, alimentação, atividade física, sono, acesso a serviços de saúde"
  }},
  "exame_fisico": {{
    "sinais_vitais": {{
      "pa": "120 x 80 mmHg", "fc": "78 bpm", "fr": "16 irpm", "tax": "36,5 °C (axilar)",
      "spo2": "98% em ar ambiente", "peso": "70 kg", "altura": "1,70 m", "imc": "24,2 kg/m²",
      "observacao": "opcional: ex. PA ortostática, achado relevante durante a aferição"
    }},
    "exame_fisico_geral": "estado geral, hidratação, coloração, orientação",
    "aparelho_cardiovascular": "ritmo, bulhas, sopros, pulsos, edemas",
    "aparelho_respiratorio": "expansibilidade, murmúrio vesicular, ruídos adventícios",
    "aparelho_abdominal": "inspeção, palpação, percussão, ausculta",
    "aparelho_osteoarticular": "articulações, marcha, força",
    "exame_neurologico": "apenas se relevante para a queixa"
  }},
  "hipoteses_diagnosticas": ["diagnóstico principal", "primeiro diferencial", "segundo diferencial se aplicável"],
  "agente_ia": {{
    "perfil": "2-3 parágrafos em terceira pessoa: como o paciente se comporta, como responde, o que não relaciona espontaneamente; coerente com os Eixos B e C",
    "voz_postura_discurso": ["itens curtos"],
    "vocabulario": ["termos leigos que usa e termos técnicos que não entende"],
    "reacoes_emocionais": ["itens curtos"],
    "omite_minimiza_distorce": ["o que omite, minimiza ou distorce, e o que dispara a revelação"],
    "temas_sensiveis": ["itens curtos"],
    "desafios_comunicacao": ["o que o estudante precisa exercitar nesta consulta"],
    "acompanhante": ["apenas se houver acompanhante; senão lista vazia"],
    "dados_so_por_interrogacao": ["informações que só aparecem se o estudante perguntar ativamente"]
  }}
}}
"""


def build_user_prompt(req: PatientGenerateRequest) -> str:
    lines = [
        f"Área clínica (Eixo A): {EIXO_A_LABELS.get(req.eixo_a, req.eixo_a)}",
        f"Perfil comportamental (Eixo B): paciente {EIXO_B_LABELS.get(req.eixo_b, req.eixo_b)}",
        f"Complexidade: {COMPLEXIDADE_LABELS.get(req.complexidade, req.complexidade)}",
        f"Perfil socioeconômico (Eixo C): {EIXO_C_LABELS.get(req.eixo_c, req.eixo_c)}",
    ]
    if req.condicao_social:
        lines.append(f"Condição social: {CONDICAO_SOCIAL_LABELS.get(req.condicao_social, req.condicao_social)}")
    if req.sexo:
        lines.append(f"Sexo: {'masculino' if req.sexo == 'M' else 'feminino'}")
    if req.faixa_etaria:
        lines.append(f"Faixa etária: {FAIXA_ETARIA_RANGE.get(req.faixa_etaria, req.faixa_etaria)}")
    if req.instrucoes_extras:
        lines.append(f"Instruções adicionais: {req.instrucoes_extras}")
    lines.append(
        "IMPORTANTE: O interrogatorio_complementar deve ter uma entrada por sistema, "
        "descrevendo o que o paciente nega E o que confirma quando perguntado "
        "especificamente sobre aquele sistema. Não misture tudo em um único texto."
    )
    lines.append(
        "O campo exame_fisico deve ter sinais vitais individuais (pa, fc, fr, tax, "
        "spo2, peso, altura, imc) além dos achados por aparelho."
    )
    lines.append(
        "O campo agente_ia deve seguir a estrutura indicada (perfil + subseções em lista), "
        "totalizando 300-500 palavras, sem repetir informações entre as subseções."
    )
    lines.append(
        "A queixa_principal deve ser a frase exata como o paciente expressaria em "
        "linguagem coloquial."
    )
    if req.eixo_c == "pediatrico":
        lines.append(
            "Paciente pediátrico: preencha identificacao.informante (responsável) e escreva a HDA e o "
            "agente_ia considerando criança e responsável como dois interlocutores."
        )
    return "\n".join(lines)


async def call_openai_generate(prompt: str) -> dict[str, Any]:
    """Chama GPT-4o e retorna o JSON do caso gerado."""
    import httpx

    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY não configurada. A geração via LLM requer a chave da API.",
        )

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": "gpt-4o",
                "response_format": {"type": "json_object"},
                "temperature": 0.9,
                "messages": [
                    {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        resp.raise_for_status()

    raw = resp.json()["choices"][0]["message"]["content"]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        log.error(f"GPT-4o retornou JSON inválido: {e}\n{raw[:500]}")
        raise HTTPException(status_code=502, detail="LLM retornou resposta malformada.")


def chunk_text(text: str) -> list[str]:
    if not text.strip():
        return []
    if len(text) <= CHUNK_SIZE:
        return [text.strip()]
    chunks, start = [], 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            search_from = start + max(CHUNK_OVERLAP, CHUNK_SIZE // 2)
            for sep in ["\n\n", "\n", ". ", " "]:
                idx = text.rfind(sep, search_from, end)
                if idx != -1:
                    end = idx + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        next_start = end - CHUNK_OVERLAP
        if next_start <= start:
            next_start = start + CHUNK_SIZE - CHUNK_OVERLAP
        start = next_start
    return chunks


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    import httpx

    if not OPENAI_API_KEY:
        return [[0.0] * EMBEDDING_DIM for _ in texts]
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={"model": EMBEDDING_MODEL, "input": texts},
        )
        resp.raise_for_status()
    return [item["embedding"] for item in resp.json()["data"]]


def next_case_number_sync(existing_numbers: list[int]) -> int:
    n = max(existing_numbers, default=0) + 1
    return n


def _lista(value: Any) -> list[str]:
    return [str(v).strip() for v in value if str(v).strip()] if isinstance(value, list) else []


def _assemble_case_data(
    *,
    nome: str, idade: int, sexo: str, queixa: str, diagnostico: str,
    ident_extras: dict[str, Any], contexto_aluno: str, hda: str,
    interrogatorio: Any, historia_fisiologica: str, patologica: dict[str, Any],
    historia_familiar: str, social: dict[str, Any], exame_fisico: Any,
    agente: Any, hipoteses: list[str], classificacao: dict[str, Any], gerado_por_llm: bool,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Monta o case_data no modelo padronizado e o texto por seção para chunking (usado por manual e LLM)."""
    interrogatorio_est, _ = normalize_interrogatorio(interrogatorio)
    exame_est, _ = normalize_exame_fisico(exame_fisico)
    agente_est, agente_texto = normalize_agente(agente)

    case_data = {
        "schema_version": SCHEMA_VERSION,
        "contexto_aluno": contexto_aluno,
        "identificacao": build_identificacao(nome, idade, sexo, ident_extras),
        "queixa_principal_texto": queixa,
        "historia_doenca_atual": hda,
        "interrogatorio_complementar": interrogatorio_est,
        "historia_fisiologica": {"texto_livre": historia_fisiologica},
        "historia_patologica": patologica,
        "historia_familiar": {"texto_livre": historia_familiar},
        "historia_social": social,
        "exame_fisico": exame_est,
        "diagnostico": {"principal": diagnostico, "fonte": "llm" if gerado_por_llm else "manual"},
        "diagnostico_completo": diagnostico,
        "hipoteses_diagnosticas": hipoteses or [diagnostico],
        "caracteristicas_agente": agente_texto,
        "agente_ia": agente_est,
        "classificacao": {k: v for k, v in classificacao.items() if v not in (None, "")},
        "raw_sections": {},
        "gerado_por_llm": gerado_por_llm,
    }
    return case_data, build_chunk_sections(case_data, case_data["hipoteses_diagnosticas"])


async def _persist_patient(
    db: AsyncSession, *, fields: dict[str, Any], case_data: dict[str, Any],
    sections: dict[str, str], generated_by: str,
) -> PatientGenerateResponse:
    """Insere paciente + chunks com embeddings e confirma a transação."""
    result = await db.execute(select(VirtualPatient.case_number))
    case_num = next_case_number_sync([row[0] for row in result.fetchall()])

    patient = VirtualPatient(case_number=case_num, case_data=case_data, **fields)
    db.add(patient)
    await db.flush()
    patient_id = patient.id
    log.info(f"  Paciente #{case_num} ({fields['nome']}) inserido — id={patient_id}")

    all_chunks: list[tuple[str, str, int]] = []
    for section_name, section_text in sections.items():
        if not section_text or not section_text.strip():
            continue
        for i, chunk in enumerate(chunk_text(section_text)):
            all_chunks.append((section_name, chunk, i))
    log.info(f"  {len(all_chunks)} chunks gerados")

    batch_size = 100
    for batch_start in range(0, len(all_chunks), batch_size):
        batch = all_chunks[batch_start: batch_start + batch_size]
        embeddings = await get_embeddings([c[1] for c in batch])  # vetores zero sem OPENAI_API_KEY
        for (section_name, content, chunk_index), embedding in zip(batch, embeddings):
            db.add(KnowledgeChunk(
                patient_id=patient_id,
                section=section_name,
                content=content,
                embedding=embedding,
                chunk_index=chunk_index,
                token_count=len(content.split()),
            ))

    await db.commit()
    log.info(f"  Ingestão completa: {len(all_chunks)} chunks para paciente #{case_num}")
    return PatientGenerateResponse(
        patient=VirtualPatientDetail.model_validate(patient),
        chunks_ingested=len(all_chunks),
        generated_by=generated_by,
    )


@router.post(
    "/generate",
    response_model=PatientGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Gera um novo paciente virtual via GPT-4o e ingere no banco",
)
async def generate_patient(
    req: PatientGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    log.info(f"Gerando paciente: eixo_a={req.eixo_a} eixo_b={req.eixo_b} complexidade={req.complexidade}")
    case_json = await call_openai_generate(build_user_prompt(req))

    nome = case_json.get("nome", "Paciente Gerado")
    idade = int(case_json.get("idade", 40))
    sexo = "M" if str(case_json.get("sexo", req.sexo or "M")).upper().startswith("M") else "F"
    queixa = case_json.get("queixa_principal", "")
    diagnostico = case_json.get("diagnostico_principal", "Não especificado")

    ident_raw = case_json.get("identificacao")
    ident_raw = ident_raw if isinstance(ident_raw, dict) else {}
    pat_raw = case_json.get("historia_patologica")
    pat_raw = pat_raw if isinstance(pat_raw, dict) else {"texto_livre": str(pat_raw or "")}
    soc_raw = case_json.get("historia_social")
    soc_raw = soc_raw if isinstance(soc_raw, dict) else {"texto_livre": str(soc_raw or "")}

    # `agente_ia` (estruturado, modelo atual) tem prioridade; `caracteristicas_agente` é o formato antigo.
    agente = case_json.get("agente_ia") or case_json.get("caracteristicas_agente", "")

    case_data, sections = _assemble_case_data(
        nome=nome, idade=idade, sexo=sexo, queixa=queixa, diagnostico=diagnostico,
        ident_extras=ident_raw,
        contexto_aluno=str(case_json.get("contexto_aluno") or "").strip(),
        hda=case_json.get("historia_doenca_atual", ""),
        interrogatorio=case_json.get("interrogatorio_complementar", {}),
        historia_fisiologica=str(case_json.get("historia_fisiologica") or ""),
        patologica={
            "doencas_previas": _lista(pat_raw.get("doencas_previas")),
            "cirurgias": _lista(pat_raw.get("cirurgias")),
            "internacoes": _lista(pat_raw.get("internacoes")),
            "medicamentos_em_uso": _lista(pat_raw.get("medicamentos_em_uso")),
            "alergias": _lista(pat_raw.get("alergias")),
            "texto_livre": str(pat_raw.get("texto_livre") or ""),
            "medicacoes_observacao": str(pat_raw.get("medicacoes_observacao") or "") or None,
        },
        historia_familiar=str(case_json.get("historia_familiar") or ""),
        social={
            "tabagismo": soc_raw.get("tabagismo"),
            "etilismo": soc_raw.get("etilismo"),
            "texto_livre": str(soc_raw.get("texto_livre") or ""),
        },
        exame_fisico=case_json.get("exame_fisico", {}),
        agente=agente,
        hipoteses=_lista(case_json.get("hipoteses_diagnosticas")),
        classificacao={
            "eixo_a": req.eixo_a, "eixo_b": req.eixo_b, "eixo_c": req.eixo_c,
            "complexidade": req.complexidade, "condicao_social": req.condicao_social,
        },
        gerado_por_llm=True,
    )
    return await _persist_patient(
        db,
        fields=dict(
            eixo_a=req.eixo_a, eixo_b=req.eixo_b, eixo_c=req.eixo_c, complexidade=req.complexidade,
            nome=nome, idade=idade, sexo=sexo, queixa_principal=queixa, diagnostico_principal=diagnostico,
        ),
        case_data=case_data, sections=sections, generated_by="gpt-4o",
    )


@router.post(
    "/manual",
    response_model=PatientGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra um paciente a partir de formulário manual (sem LLM)",
)
async def create_patient_manual(
    req: PatientManualRequest,
    db: AsyncSession = Depends(get_db),
):
    agente = req.agente_ia if req.agente_ia else (req.caracteristicas_agente or "")
    case_data, sections = _assemble_case_data(
        nome=req.nome, idade=req.idade, sexo=req.sexo, queixa=req.queixa_principal,
        diagnostico=req.diagnostico_principal,
        ident_extras=req.model_dump(include={
            "cor", "estado_civil", "profissao", "religiao", "residencia", "naturalidade", "nacionalidade",
            "profissao_anterior", "ocupacao", "escolaridade", "residencias_anteriores", "informante",
        }),
        contexto_aluno=(req.contexto_aluno or "").strip(),
        hda=req.historia_doenca_atual,
        interrogatorio=req.interrogatorio_complementar or {},
        historia_fisiologica=req.historia_fisiologica or "",
        patologica={
            "doencas_previas": req.doencas_previas,
            "cirurgias": req.cirurgias,
            "internacoes": req.internacoes,
            "medicamentos_em_uso": req.medicamentos_em_uso,
            "alergias": req.alergias,
            "texto_livre": req.historia_patologica_texto or "",
            "medicacoes_observacao": req.medicacoes_observacao or None,
        },
        historia_familiar=req.historia_familiar or "",
        social={
            "tabagismo": req.tabagismo,
            "etilismo": req.etilismo,
            "texto_livre": req.historia_social_texto or "",
        },
        exame_fisico=req.exame_fisico or "",
        agente=agente,
        hipoteses=req.hipoteses_diagnosticas,
        classificacao={
            "eixo_a": req.eixo_a, "eixo_b": req.eixo_b, "eixo_c": req.eixo_c,
            "complexidade": req.complexidade, "letramento": req.letramento,
            "condicao_social": req.condicao_social, "nuance_eixo_b": req.nuance_eixo_b,
        },
        gerado_por_llm=False,
    )
    return await _persist_patient(
        db,
        fields=dict(
            eixo_a=req.eixo_a, eixo_b=req.eixo_b, eixo_c=req.eixo_c, complexidade=req.complexidade,
            nome=req.nome, idade=req.idade, sexo=req.sexo, queixa_principal=req.queixa_principal,
            diagnostico_principal=req.diagnostico_principal,
        ),
        case_data=case_data, sections=sections, generated_by="manual",
    )


_REQUIRED_DOCX_FIELDS = {
    "nome": "Nome do paciente",
    "idade": "Idade",
    "sexo": "Sexo (M ou F)",
    "queixa_principal": "Queixa principal",
    "diagnostico_principal": "Diagnóstico principal",
    "historia_doenca_atual": "História da doença atual",
    "eixo_a": "Área clínica (Eixo A)",
}

_OPTIONAL_DOCX_FIELDS = {
    "contexto_aluno": "Contexto para o aluno",
    "exame_fisico": "Exame físico",
    "interrogatorio_complementar": "Interrogatório complementar",
    "historia_fisiologica": "Antecedentes fisiológicos",
    "historia_patologica_texto": "Antecedentes patológicos",
    "historia_familiar": "Antecedentes familiares",
    "historia_social_texto": "Hábitos de vida",
    "agente_ia": "Características do agente de IA",
}

# Subseções do agente que o modelo padronizado sempre traz ("acompanhante" só quando há acompanhante).
_AGENTE_ESPERADAS = [k for k, _ in AGENTE_SECOES if k != "acompanhante"]


def _has_content(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_has_content(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_content(v) for v in value)
    return bool(value) and len(str(value).strip()) >= 5


def extract_manual_fields(raw_text: str) -> dict[str, Any]:
    """Texto do DOCX -> campos no shape de PatientManualRequest (reusa o parser da ingestão)."""
    from scripts.ingest.case_parser import (
        infer_eixo_c, labeled_blocks, map_complexidade, map_eixo_a, map_eixo_b,
        parse_case, short_diagnosis,
    )
    from scripts.ingest.case_structure import (
        structure_agente, structure_exame_fisico, structure_interrogatorio,
        structure_medicacoes, structure_patologica, structure_social,
    )

    parsed = parse_case(raw_text)
    sec, meta, ident, dx = parsed["sections"], parsed["metadados"], parsed["identificacao"], parsed["diagnostico"]
    patologica = structure_patologica(sec.get("historia_patologica", ""), labeled_blocks(sec.get("historia_patologica", "")))
    social = structure_social(sec.get("historia_social", ""), labeled_blocks(sec.get("historia_social", "")))
    meds = structure_medicacoes(sec["medicacoes_em_uso"]) if sec.get("medicacoes_em_uso") else {}
    eixo_c, _ = infer_eixo_c(meta.get("eixo_c_bruto", ""), ident.get("idade_meses"), ident.get("escolaridade", ""))
    queixa = sec.get("queixa_principal", "") or meta.get("queixa_bruta", "")
    queixa = queixa.split("\n\n")[0].strip() if queixa else ""

    # Interrogatório/exame: dict por sistema/aparelho; sem rótulos reconhecíveis, o texto original.
    interrogatorio = structure_interrogatorio(sec.get("interrogatorio_complementar", ""), parsed["interrogatorio"])
    if set(interrogatorio) <= {"texto"}:
        interrogatorio = interrogatorio.get("texto", "")
    exame = {k: v for k, v in structure_exame_fisico(sec.get("exame_fisico", ""), parsed["exame_fisico_blocos"]).items()
             if k != "texto_livre"}
    if not exame or set(exame) <= {"introducao"}:
        exame = sec.get("exame_fisico", "")

    return {
        "eixo_a": map_eixo_a(meta.get("eixo_a_bruto", "")) or "",
        "eixo_b": map_eixo_b(meta.get("eixo_b_bruto", "")) or "colaborativo",
        "eixo_c": eixo_c or "baixo_letramento_vulneravel",
        "complexidade": map_complexidade(meta.get("complexidade_bruta", "")) or "media",
        "letramento": meta.get("eixo_c_letramento", ""),
        "condicao_social": meta.get("eixo_c_condicao_social", ""),
        "nuance_eixo_b": meta.get("eixo_b_nuance", ""),
        "nome": ident.get("nome", ""),
        "idade": ident.get("idade"),
        "sexo": ident.get("sexo", ""),
        "cor": ident.get("cor", ""),
        "estado_civil": ident.get("estado_civil", ""),
        "profissao": ident.get("profissao", ""),
        "religiao": ident.get("religiao", ""),
        "residencia": ident.get("residencia", ""),
        "naturalidade": ident.get("naturalidade", ""),
        "nacionalidade": ident.get("nacionalidade", ""),
        "profissao_anterior": ident.get("profissao_anterior", ""),
        "ocupacao": ident.get("ocupacao", ""),
        "escolaridade": ident.get("escolaridade", ""),
        "residencias_anteriores": ident.get("residencias_anteriores", ""),
        "informante": ident.get("informante", ""),
        "contexto_aluno": sec.get("contexto_aluno", ""),
        "queixa_principal": queixa,
        "diagnostico_principal": short_diagnosis(dx["principal"]) if dx and dx.get("principal") else "",
        "historia_doenca_atual": sec.get("historia_doenca_atual", ""),
        "interrogatorio_complementar": interrogatorio,
        "historia_fisiologica": sec.get("historia_fisiologica", ""),
        "historia_familiar": sec.get("historia_familiar", ""),
        "historia_social_texto": sec.get("historia_social", ""),
        "tabagismo": social.get("tabagismo", ""),
        "etilismo": social.get("etilismo", ""),
        "exame_fisico": exame,
        "agente_ia": structure_agente(sec.get("caracteristicas_agente", "")),
        "hipoteses_diagnosticas": list(dx.get("hipoteses") or []) if dx else [],
        "historia_patologica_texto": patologica.get("texto_livre", ""),
        "doencas_previas": patologica.get("doencas_previas", []),
        "cirurgias": patologica.get("cirurgias", []),
        "internacoes": patologica.get("internacoes", []),
        "medicamentos_em_uso": meds.get("itens") or patologica.get("medicamentos_em_uso", []),
        "medicacoes_observacao": meds.get("observacao", ""),
        "alergias": patologica.get("alergias", []),
    }


def validate_extracted(extracted: dict[str, Any]) -> list[DocxValidationIssue]:
    issues: list[DocxValidationIssue] = []

    def add(field: str, severity: str, message: str) -> None:
        issues.append(DocxValidationIssue(field=field, severity=severity, message=message))

    for field, label in _REQUIRED_DOCX_FIELDS.items():
        val = extracted.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            add(field, "error", f"{label} não encontrado no documento")
        elif field == "historia_doenca_atual" and len(val) < 50:
            add(field, "error", f"História da doença atual muito curta ({len(val)} caracteres, mínimo 50)")
        elif field == "sexo" and val not in ("M", "F"):
            add(field, "error", f"Sexo inválido: '{val}'. Use M ou F")
        elif field == "nome" and len(val.strip()) < 2:
            add(field, "error", "Nome muito curto (mínimo 2 caracteres)")
        elif field == "queixa_principal" and len(val.strip()) < 5:
            add(field, "error", "Queixa principal muito curta (mínimo 5 caracteres)")
        elif field == "diagnostico_principal" and len(val.strip()) < 3:
            add(field, "error", "Diagnóstico principal muito curto (mínimo 3 caracteres)")
        elif field == "idade" and not 0 <= val <= 130:
            add(field, "error", f"Idade fora do intervalo (0–130): {val}")
        elif field == "eixo_a" and val not in EIXO_A_LABELS:
            add(field, "error", f"Área clínica '{val}' não reconhecida — selecione o Eixo A")

    for field, label in _OPTIONAL_DOCX_FIELDS.items():
        if not _has_content(extracted.get(field)):
            add(field, "warning", f"{label} ausente ou muito curto")

    # Completude do modelo padronizado: sistemas do interrogatório, sinais vitais, subseções do agente.
    interrogatorio = extracted.get("interrogatorio_complementar")
    if isinstance(interrogatorio, dict) and _has_content(interrogatorio):
        faltam = [label for key, label in SISTEMAS if not _has_content(interrogatorio.get(key))]
        if faltam:
            add("interrogatorio_complementar", "warning", "Interrogatório sem: " + ", ".join(faltam))
    exame = extracted.get("exame_fisico")
    if isinstance(exame, dict) and _has_content(exame) and not exame.get("sinais_vitais"):
        add("exame_fisico", "warning", "Sinais vitais não encontrados no exame físico")
    agente = extracted.get("agente_ia")
    if isinstance(agente, dict) and _has_content(agente):
        faltam = [label for key, label in AGENTE_SECOES if key in _AGENTE_ESPERADAS and not _has_content(agente.get(key))]
        if faltam:
            add("agente_ia", "warning", "Agente de IA sem: " + ", ".join(faltam))
    if not extracted.get("medicamentos_em_uso") and not _has_content(extracted.get("medicacoes_observacao")):
        add("medicamentos_em_uso", "warning", "Medicações em uso não encontradas (seção 6)")
    return issues


@router.post(
    "/parse-docx",
    response_model=DocxParseResponse,
    summary="Extrai os campos de um DOCX e lista problemas (não grava no banco)",
)
async def parse_docx_preview(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Apenas arquivos .docx são aceitos")

    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from scripts.ingest.ingest_cases import docx_to_text
        extracted = extract_manual_fields(docx_to_text(Path(tmp_path)))
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Erro ao processar DOCX: pandoc não está instalado no servidor")
    except Exception as e:
        log.error(f"parse-docx error: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao processar DOCX: {e}")
    finally:
        os.unlink(tmp_path)

    issues = validate_extracted(extracted)
    return DocxParseResponse(
        extracted=extracted,
        issues=issues,
        can_save=not any(i.severity == "error" for i in issues),
    )
