# backend/app/modules/patient/router.py
"""
Módulo de geração de pacientes virtuais via LLM (GPT-4o).

POST /api/v1/patients/generate
  - Recebe parâmetros clínicos
  - Gera o caso completo via GPT-4o (JSON estruturado)
  - Chuca texto → chunks → embeddings → PostgreSQL
  - Retorna o paciente criado + nº de chunks ingeridos
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import KnowledgeChunk, VirtualPatient
from app.schemas.patient import PatientGenerateRequest, PatientGenerateResponse, VirtualPatientDetail, VirtualPatientResponse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/patients", tags=["patients"])

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
EMBEDDING_DIM = 1536
EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

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

FAIXA_ETARIA_RANGE = {
    "crianca": "entre 3 e 12 anos",
    "adolescente": "entre 13 e 17 anos",
    "adulto": "entre 18 e 59 anos",
    "idoso": "entre 60 e 85 anos",
}

# Rótulos usados para expandir o interrogatório complementar (sistema a sistema)
# e o exame físico estruturado em texto legível para chunking/embeddings.
SISTEMA_LABELS = {
    "cabeca": "Cabeça",
    "olhos": "Olhos",
    "ouvidos": "Ouvidos",
    "nariz_boca_garganta": "Nariz, boca e garganta",
    "pescoco": "Pescoço",
    "aparelho_respiratorio_circulatorio": "Aparelho respiratório e circulatório",
    "aparelho_digestivo": "Aparelho digestivo",
    "aparelho_geniturinario": "Aparelho geniturinário",
    "aparelho_locomotor": "Aparelho locomotor",
    "pele": "Pele",
    "sistema_nervoso": "Sistema nervoso",
    "sintomas_gerais": "Sintomas gerais",
}

SINAIS_VITAIS_LABELS = {
    "pa": "PA", "fc": "FC", "fr": "FR", "tax": "Tax", "spo2": "SpO2",
    "peso": "Peso", "altura": "Altura", "imc": "IMC",
}

EXAME_FISICO_LABELS = {
    "geral": "Estado geral",
    "cardiovascular": "Aparelho cardiovascular",
    "respiratorio": "Aparelho respiratório",
    "abdome": "Abdome",
    "neurologico": "Exame neurológico",
    "outros": "Outros achados",
}

GENERATION_SYSTEM_PROMPT = """\
Você é um especialista em semiologia médica e educação médica da UFPI.
Sua tarefa é criar um caso clínico sintético, realista e educacionalmente rico
para treinamento de anamnese por estudantes de medicina.

O caso deve:
- Ser clinicamente coerente e compatível com a prática médica brasileira
- Usar linguagem coloquial para as falas do paciente (sem jargão técnico)
- Incluir detalhes sociais, culturais e emocionais que tornem o personagem verossímil
- Conter informações suficientes para uma anamnese completa de 20-30 min
- NÃO revelar o diagnóstico diretamente — o paciente não sabe o diagnóstico

Retorne APENAS um objeto JSON válido com exatamente esta estrutura (sem markdown, sem explicações):

{
  "nome": "Nome completo brasileiro",
  "idade": 45,
  "sexo": "M" ou "F",
  "queixa_principal": "frase curta exatamente como o paciente diria, entre aspas simples no texto",
  "diagnostico_principal": "diagnóstico correto para o professor",
  "historia_doenca_atual": "narrativa detalhada em terceira pessoa (400-600 palavras). Inclua: início, duração, evolução, fatores de melhora/piora, sintomas associados, medicamentos em uso se relevante, comportamento do paciente frente à doença",
  "identificacao": {
    "cor": "parda/branca/preta/amarela/indígena",
    "estado_civil": "casado/solteiro/viúvo/divorciado",
    "profissao": "profissão atual realista",
    "religiao": "religião",
    "residencia": "cidade e bairro piauiense ou nordestino",
    "naturalidade": "cidade de origem"
  },
  "interrogatorio_complementar": {
    "cabeca": "o que nega ou confirma sobre cefaleia, tonturas",
    "olhos": "o que nega ou confirma",
    "ouvidos": "o que nega ou confirma",
    "nariz_boca_garganta": "o que nega ou confirma",
    "pescoco": "o que nega ou confirma",
    "aparelho_respiratorio_circulatorio": "o que nega ou confirma sobre tosse, dispneia, dor torácica, palpitações",
    "aparelho_digestivo": "o que nega ou confirma sobre náuseas, vômitos, alteração do hábito intestinal, icterícia",
    "aparelho_geniturinario": "o que nega ou confirma",
    "aparelho_locomotor": "o que nega ou confirma",
    "pele": "o que nega ou confirma",
    "sistema_nervoso": "o que nega ou confirma sobre convulsões, paresias, alterações sensitivas",
    "sintomas_gerais": "febre, emagrecimento, astenia, sudorese noturna"
  },
  "historia_fisiologica": "texto sobre gestações, partos, desenvolvimento, puberdade, menopausa se aplicável",
  "historia_patologica": {
    "doencas_previas": ["lista de doenças pregressas"],
    "cirurgias": ["lista ou 'nega cirurgias'"],
    "internacoes": ["lista ou 'nega internações'"],
    "medicamentos_em_uso": ["medicamento dose frequência"],
    "alergias": ["lista ou 'nega alergias'"],
    "texto_livre": "detalhes adicionais, vacinas, doenças da infância"
  },
  "historia_familiar": "saúde detalhada dos pais (causa e idade do óbito se falecidos), irmãos, filhos — doenças prevalentes",
  "historia_social": {
    "tabagismo": "ex-tabagista X maços-ano / tabagista X cigarros/dia há Y anos / nega tabagismo",
    "etilismo": "descrição quantificada do uso de álcool",
    "texto_livre": "escolaridade, condições de moradia, saneamento, renda, com quem mora, atividade física, alimentação, acesso a serviços de saúde"
  },
  "exame_fisico": {
    "sinais_vitais": {
      "pa": "120/80 mmHg",
      "fc": "78 bpm",
      "fr": "16 irpm",
      "tax": "36,5°C",
      "spo2": "98% em ar ambiente",
      "peso": "70 kg",
      "altura": "1,70 m",
      "imc": "24,2 kg/m²"
    },
    "geral": "estado geral, hidratação, coloração, orientação",
    "cardiovascular": "ritmo, bulhas, sopros, pulsos, edemas",
    "respiratorio": "expansibilidade, murmúrio vesicular, ruídos adventícios",
    "abdome": "inspeção, palpação, percussão, ausculta",
    "neurologico": "consciência, orientação, força, sensibilidade, reflexos se relevante",
    "outros": "achados específicos do sistema acometido pela queixa principal"
  },
  "hipoteses_diagnosticas": ["diagnóstico principal", "primeiro diferencial", "segundo diferencial se aplicável"],
  "caracteristicas_agente": "3 parágrafos detalhados: (1) Como o paciente se comporta ao entrar, postura, tom de voz, nível de ansiedade, relação com o médico. (2) Como responde às perguntas — o que relata espontaneamente, o que omite, o que exagera, termos leigos que usa para descrever sintomas, como reage a perguntas técnicas. (3) Informações que o estudante precisa explorar ativamente pois o paciente não oferece espontaneamente. Deve ser coerente com o Eixo B (perfil comportamental) e o Eixo C (letramento). Escrito em terceira pessoa."
}
"""


def build_user_prompt(req: PatientGenerateRequest) -> str:
    lines = [
        f"Área clínica (Eixo A): {EIXO_A_LABELS.get(req.eixo_a, req.eixo_a)}",
        f"Perfil comportamental (Eixo B): paciente {EIXO_B_LABELS.get(req.eixo_b, req.eixo_b)}",
        f"Complexidade: {COMPLEXIDADE_LABELS.get(req.complexidade, req.complexidade)}",
        f"Perfil socioeconômico (Eixo C): {EIXO_C_LABELS.get(req.eixo_c, req.eixo_c)}",
    ]
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
        "O campo caracteristicas_agente deve ter 3 parágrafos distintos conforme "
        "instruído, totalizando 300-500 palavras."
    )
    lines.append(
        "A queixa_principal deve ser a frase exata como o paciente expressaria em "
        "linguagem coloquial."
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


def format_interrogatorio_complementar(raw: Any) -> tuple[dict[str, str], str]:
    """Normaliza o interrogatório complementar retornado pelo LLM.

    Formato novo (esperado): dict com uma chave por sistema.
    Formato antigo (fallback): string única — mantida como compatibilidade.

    Retorna (estrutura para case_data, texto concatenado para chunking).
    """
    if isinstance(raw, dict):
        estruturado = {k: str(v) for k, v in raw.items() if v}
        texto = "\n\n".join(
            f"{SISTEMA_LABELS.get(k, k.replace('_', ' ').capitalize())}: {v}"
            for k, v in estruturado.items()
        )
        return estruturado, texto
    texto = str(raw).strip() if raw else ""
    return ({"texto": texto} if texto else {}), texto


def format_exame_fisico(raw: Any) -> tuple[dict[str, Any], str]:
    """Normaliza o exame físico retornado pelo LLM.

    Formato novo (esperado): dict com `sinais_vitais` (dict) + achados por aparelho.
    Formato antigo (fallback): string única — mantida como compatibilidade.

    Retorna (estrutura para case_data, texto concatenado para chunking).
    """
    if isinstance(raw, dict):
        sinais_vitais = raw.get("sinais_vitais")
        sinais_vitais = sinais_vitais if isinstance(sinais_vitais, dict) else {}
        partes = []
        sv_texto = ", ".join(
            f"{SINAIS_VITAIS_LABELS.get(k, k.upper())}: {v}"
            for k, v in sinais_vitais.items() if v
        )
        if sv_texto:
            partes.append(f"Sinais vitais: {sv_texto}")
        for k, v in raw.items():
            if k == "sinais_vitais" or not v:
                continue
            partes.append(f"{EXAME_FISICO_LABELS.get(k, k.replace('_', ' ').capitalize())}: {v}")
        texto = "\n\n".join(partes)
        estruturado = dict(raw)
        estruturado["texto_livre"] = texto
        return estruturado, texto
    texto = str(raw).strip() if raw else ""
    return {"texto_livre": texto}, texto


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
    # 1. Gerar caso via LLM
    log.info(f"Gerando paciente: eixo_a={req.eixo_a} eixo_b={req.eixo_b} complexidade={req.complexidade}")
    user_prompt = build_user_prompt(req)
    case_json = await call_openai_generate(user_prompt)

    # 2. Extrair campos obrigatórios com fallbacks seguros
    nome = case_json.get("nome", "Paciente Gerado")
    idade = int(case_json.get("idade", 40))
    sexo_raw = case_json.get("sexo", req.sexo or "M")
    sexo = "M" if str(sexo_raw).upper().startswith("M") else "F"
    queixa = case_json.get("queixa_principal", "")
    diagnostico = case_json.get("diagnostico_principal", "Não especificado")

    ident_raw = case_json.get("identificacao", {})
    historia_pat_raw = case_json.get("historia_patologica", {})
    historia_soc_raw = case_json.get("historia_social", {})

    interrogatorio_estruturado, interrogatorio_texto = format_interrogatorio_complementar(
        case_json.get("interrogatorio_complementar", {})
    )
    exame_estruturado, exame_texto = format_exame_fisico(case_json.get("exame_fisico", {}))
    caracteristicas_agente = case_json.get("caracteristicas_agente", "")

    case_data = {
        "identificacao": {
            "nome": nome, "idade": idade, "sexo": sexo,
            "cor": ident_raw.get("cor"),
            "estado_civil": ident_raw.get("estado_civil"),
            "profissao": ident_raw.get("profissao"),
            "religiao": ident_raw.get("religiao"),
            "residencia": ident_raw.get("residencia"),
            "naturalidade": ident_raw.get("naturalidade"),
        },
        "queixa_principal_texto": queixa,
        "historia_doenca_atual": case_json.get("historia_doenca_atual", ""),
        "interrogatorio_complementar": interrogatorio_estruturado,
        "historia_fisiologica": {"texto_livre": case_json.get("historia_fisiologica", "")},
        "historia_patologica": {
            "doencas_previas": historia_pat_raw.get("doencas_previas", []) if isinstance(historia_pat_raw, dict) else [],
            "cirurgias": historia_pat_raw.get("cirurgias", []) if isinstance(historia_pat_raw, dict) else [],
            "internacoes": historia_pat_raw.get("internacoes", []) if isinstance(historia_pat_raw, dict) else [],
            "medicamentos_em_uso": historia_pat_raw.get("medicamentos_em_uso", []) if isinstance(historia_pat_raw, dict) else [],
            "alergias": historia_pat_raw.get("alergias", []) if isinstance(historia_pat_raw, dict) else [],
            "texto_livre": historia_pat_raw.get("texto_livre", "") if isinstance(historia_pat_raw, dict) else str(historia_pat_raw),
        },
        "historia_familiar": {"texto_livre": case_json.get("historia_familiar", "")},
        "historia_social": {
            "tabagismo": historia_soc_raw.get("tabagismo") if isinstance(historia_soc_raw, dict) else None,
            "etilismo": historia_soc_raw.get("etilismo") if isinstance(historia_soc_raw, dict) else None,
            "texto_livre": historia_soc_raw.get("texto_livre", "") if isinstance(historia_soc_raw, dict) else str(historia_soc_raw),
        },
        "exame_fisico": exame_estruturado,
        "diagnostico_completo": diagnostico,
        "hipoteses_diagnosticas": case_json.get("hipoteses_diagnosticas", [diagnostico]),
        "caracteristicas_agente": caracteristicas_agente,
        "raw_sections": {},
        "gerado_por_llm": True,
    }

    # 3. Determinar próximo case_number
    result = await db.execute(select(VirtualPatient.case_number))
    existing_numbers = [row[0] for row in result.fetchall()]
    case_num = next_case_number_sync(existing_numbers)

    # 4. Inserir paciente via ORM
    patient = VirtualPatient(
        case_number=case_num,
        eixo_a=req.eixo_a,
        eixo_b=req.eixo_b,
        eixo_c=req.eixo_c,
        complexidade=req.complexidade,
        nome=nome,
        idade=idade,
        sexo=sexo,
        queixa_principal=queixa,
        diagnostico_principal=diagnostico,
        case_data=case_data,
    )
    db.add(patient)
    await db.flush()
    patient_id = patient.id
    log.info(f"  Paciente #{case_num} ({nome}) inserido — id={patient_id}")

    # 5. Construir chunks das seções textuais
    sections = {
        "identificacao": f"Nome: {nome}. Idade: {idade} anos. Sexo: {'Masculino' if sexo == 'M' else 'Feminino'}.",
        "queixa_principal": queixa,
        "historia_doenca_atual": case_json.get("historia_doenca_atual", ""),
        "interrogatorio_complementar": interrogatorio_texto,
        "historia_fisiologica": case_json.get("historia_fisiologica", ""),
        "historia_patologica": (
            historia_pat_raw.get("texto_livre", "") if isinstance(historia_pat_raw, dict) else str(historia_pat_raw)
        ) + "\n" + ", ".join(
            historia_pat_raw.get("medicamentos_em_uso", []) if isinstance(historia_pat_raw, dict) else []
        ),
        "historia_familiar": case_json.get("historia_familiar", ""),
        "historia_social": (
            historia_soc_raw.get("texto_livre", "") if isinstance(historia_soc_raw, dict) else str(historia_soc_raw)
        ),
        "exame_fisico": exame_texto,
        "caracteristicas_agente": caracteristicas_agente,
        "hipoteses_diagnosticas": " | ".join(
            case_json.get("hipoteses_diagnosticas", [])
        ),
    }

    all_chunks: list[tuple[str, str, int]] = []
    for section_name, section_text in sections.items():
        if not section_text or not section_text.strip():
            continue
        for i, chunk in enumerate(chunk_text(section_text)):
            all_chunks.append((section_name, chunk, i))

    log.info(f"  {len(all_chunks)} chunks gerados")

    # 6. Embeddings e inserção em lotes
    batch_size = 100
    for batch_start in range(0, len(all_chunks), batch_size):
        batch = all_chunks[batch_start: batch_start + batch_size]
        embeddings = await get_embeddings([c[1] for c in batch])
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
        generated_by="gpt-4o",
    )
