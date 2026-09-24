#!/usr/bin/env python3
"""
backend/scripts/ingest/ingest_cases.py
---------------------------------------
Ingestion pipeline: DOCX clinical cases -> structured JSON -> pgvector

Usage:
    python -m scripts.ingest.ingest_cases --cases-dir data/cases/
    python -m scripts.ingest.ingest_cases --cases-dir data/cases/ --reset
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.models import VirtualPatient, KnowledgeChunk

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/anamnese_facil")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM = 1536
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

EIXO_A_MAP = {
    "cardiovascular": "cardiovascular",
    "respiratório": "respiratorio", "respiratorio": "respiratorio",
    "gastrointestinal": "gastrointestinal",
    "neurológico": "neurologico", "neurologico": "neurologico",
    "musculoesquelético": "musculoesqueletico", "musculoesqueletico": "musculoesqueletico",
    "endócrino/metabólico": "endocrino_metabolico", "endocrino/metabolico": "endocrino_metabolico", "endocrino_metabolico": "endocrino_metabolico",
    "geniturinário": "geniturinario", "geniturinario": "geniturinario",
}

EIXO_B_MAP = {
    "colaborativo": "colaborativo", "ansioso": "ansioso",
    "resistente": "resistente", "confuso": "confuso", "minimizador": "minimizador",
}

COMPLEXIDADE_MAP = {"baixa": "baixa", "média": "media", "media": "media", "alta": "alta"}
SEXO_MAP = {"m": "M", "masculino": "M", "f": "F", "feminino": "F"}

SECTION_PATTERNS = [
    (r"(?i)identifica[cç][aã]o", "identificacao"),
    (r"(?i)queixa\s+principal", "queixa_principal"),
    (r"(?i)hist[oó]ria\s+da\s+doen[cç]a\s+atual", "historia_doenca_atual"),
    (r"(?i)interrogat[oó]rio\s+complementar", "interrogatorio_complementar"),
    (r"(?i)hist[oó]ria\s+fisiol[oó]gica", "historia_fisiologica"),
    (r"(?i)hist[oó]ria\s+patol[oó]gica", "historia_patologica"),
    (r"(?i)hist[oó]ria\s+familiar", "historia_familiar"),
    (r"(?i)hist[oó]ria\s+social", "historia_social"),
    (r"(?i)exame\s+f[ií]sico", "exame_fisico"),
    (r"(?i)caracter[ií]sticas\s+do\s+agente", "caracteristicas_agente"),
    (r"(?i)hip[oó]teses?\s+diagn[oó]sticas?", "hipoteses_diagnosticas"),
    (r"(?i)diagn[oó]stico", "diagnostico"),
]

KNOWN_CASES = {
    1: {"nome": "Alfonso", "idade": 78, "sexo": "M", "eixo_a": "cardiovascular", "eixo_b": "colaborativo", "complexidade": "alta", "diagnostico_principal": "Hipotensão Postural", "queixa_principal": "Síncope"},
    2: {"nome": "Roberto", "idade": 16, "sexo": "M", "eixo_a": "respiratorio", "eixo_b": "colaborativo", "complexidade": "baixa", "diagnostico_principal": "Asma", "queixa_principal": "Tosse"},
    3: {"nome": "Dulce", "idade": 58, "sexo": "F", "eixo_a": "gastrointestinal", "eixo_b": "colaborativo", "complexidade": "media", "diagnostico_principal": "DRGE", "queixa_principal": "Dispepsia"},
    4: {"nome": "Eliane", "idade": 42, "sexo": "F", "eixo_a": "neurologico", "eixo_b": "colaborativo", "complexidade": "alta", "diagnostico_principal": "Migrânea", "queixa_principal": "Cefaleia"},
    5: {"nome": "Ronaldo", "idade": 62, "sexo": "M", "eixo_a": "musculoesqueletico", "eixo_b": "colaborativo", "complexidade": "baixa", "diagnostico_principal": "Gota", "queixa_principal": "Podagra"},
    6: {"nome": "Lívio", "idade": 8, "sexo": "M", "eixo_a": "endocrino_metabolico", "eixo_b": "colaborativo", "complexidade": "alta", "diagnostico_principal": "DM1", "queixa_principal": "Sonolência"},
    7: {"nome": "Luna", "idade": 38, "sexo": "F", "eixo_a": "geniturinario", "eixo_b": "colaborativo", "complexidade": "baixa", "diagnostico_principal": "ITU", "queixa_principal": "Disúria"},
    8: {"nome": "Olívia", "idade": 21, "sexo": "F", "eixo_a": "cardiovascular", "eixo_b": "colaborativo", "complexidade": "media", "diagnostico_principal": "POTS", "queixa_principal": "Palpitação"},
    9: {"nome": "Jorge", "idade": 44, "sexo": "M", "eixo_a": "respiratorio", "eixo_b": "colaborativo", "complexidade": "media", "diagnostico_principal": "Tuberculose", "queixa_principal": "Hemoptise"},
    10: {"nome": "Maria", "idade": 64, "sexo": "F", "eixo_a": "gastrointestinal", "eixo_b": "colaborativo", "complexidade": "alta", "diagnostico_principal": "Coledocolitíase", "queixa_principal": "Dor Abdominal"},
}


def docx_to_text(docx_path: Path) -> str:
    result = subprocess.run(
        ["pandoc", str(docx_path), "-t", "plain", "--wrap=none"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def clean(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def split_into_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    lines = text.split("\n")
    current_key = "preambulo"
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        is_heading = (
            (len(stripped) < 80 and stripped.isupper() and len(stripped) > 3)
            or (stripped.endswith(":") and len(stripped) < 60)
            or re.match(r"^\d+[\.)\s]", stripped)
        )
        matched_key = None
        if is_heading or len(stripped) < 60:
            for pattern, key in SECTION_PATTERNS:
                if re.search(pattern, stripped):
                    matched_key = key
                    break
        if matched_key:
            if current_lines:
                sections[current_key] = clean("\n".join(current_lines))
            current_key = matched_key
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections[current_key] = clean("\n".join(current_lines))
    return sections


def parse_metadata_from_text(text: str) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    m = re.search(r"(?i)caso\s+n[uo]?[°ºr]?\s*[:.]?\s*(\d+)", text)
    if m:
        meta["case_number"] = int(m.group(1))
    m = re.search(r"(?i)eixo\s+a\s*[:–-]?\s*(.+)", text)
    if m:
        raw = m.group(1).strip().lower().split("\n")[0]
        meta["eixo_a"] = EIXO_A_MAP.get(raw, raw)
    m = re.search(r"(?i)eixo\s+b\s*[:–-]?\s*(.+)", text)
    if m:
        raw = m.group(1).strip().lower().split("\n")[0]
        meta["eixo_b"] = EIXO_B_MAP.get(raw, "colaborativo")
    m = re.search(r"(?i)complexidade\s*[:–-]?\s*(\w+)", text)
    if m:
        raw = m.group(1).strip().lower()
        meta["complexidade"] = COMPLEXIDADE_MAP.get(raw, "media")
    return meta


def parse_identificacao(text: str) -> dict[str, Any]:
    fields = {}
    patterns = {
        "nome": r"(?i)nome\s*[:–-]?\s*(.+)",
        "idade": r"(?i)idade\s*[:–-]?\s*(\d+)",
        "sexo": r"(?i)sexo\s*[:–-]?\s*(\w+)",
        "cor": r"(?i)cor\s*[:–-]?\s*(.+)",
        "estado_civil": r"(?i)estado\s+civil\s*[:–-]?\s*(.+)",
        "profissao": r"(?i)profiss[aã]o\s*[:–-]?\s*(.+)",
        "religiao": r"(?i)religi[aã]o\s*[:–-]?\s*(.+)",
        "residencia": r"(?i)resid[eê]ncia\s*[:–-]?\s*(.+)",
    }
    for field, pattern in patterns.items():
        m = re.search(pattern, text)
        if m:
            val = m.group(1).strip().split("\n")[0].strip()
            if field == "idade":
                try:
                    fields[field] = int(val)
                except ValueError:
                    pass
            elif field == "sexo":
                fields[field] = SEXO_MAP.get(val.lower(), val)
            else:
                fields[field] = val
    return fields


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if not text.strip():
        return []
    if len(text) <= chunk_size:
        return [text.strip()]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # Search for natural break point, but only in the LAST quarter of the window
        # to guarantee we always advance by at least chunk_size - overlap chars
        if end < len(text):
            search_from = start + max(overlap, chunk_size // 2)
            for sep in ["\n\n", "\n", ". ", " "]:
                idx = text.rfind(sep, search_from, end)
                if idx != -1:
                    end = idx + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        next_start = end - overlap
        if next_start <= start:  # guarantee forward progress always
            next_start = start + chunk_size - overlap
        start = next_start
    return chunks


async def get_embeddings(texts: list[str], api_key: str) -> list[list[float]]:
    if not api_key:
        log.warning("OPENAI_API_KEY not set — using zero vectors (dev mode)")
        return [[0.0] * EMBEDDING_DIM for _ in texts]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": EMBEDDING_MODEL, "input": texts},
            timeout=60.0,
        )
        resp.raise_for_status()
        return [item["embedding"] for item in resp.json()["data"]]


async def ingest_case(docx_path: Path, session: AsyncSession, api_key: str) -> None:
    log.info(f"Processing: {docx_path.name}")
    try:
        raw_text = docx_to_text(docx_path)
    except subprocess.CalledProcessError as e:
        log.error(f"pandoc failed for {docx_path}: {e}")
        return

    sections = split_into_sections(raw_text)
    meta = parse_metadata_from_text(raw_text)

    # Always derive case_number from filename — it is the canonical source.
    # The content may have wrong/shifted numbering (e.g. Caso_6.docx saying "Caso 7" inside).
    m = re.search(r"Caso[_\s]?(\d+)", docx_path.stem, re.I)
    if m:
        case_num = int(m.group(1))
        if meta.get("case_number") and meta["case_number"] != case_num:
            log.warning(
                f"  Filename says case #{case_num} but content says #{meta['case_number']} — using filename"
            )
    elif "case_number" in meta:
        case_num = meta["case_number"]
    else:
        log.error(f"Cannot determine case number for {docx_path.name}")
        return
    known = KNOWN_CASES.get(case_num, {})
    eixo_a = known.get("eixo_a") or meta.get("eixo_a", "cardiovascular")
    eixo_b = known.get("eixo_b") or meta.get("eixo_b", "colaborativo")
    complexidade = known.get("complexidade") or meta.get("complexidade", "media")
    ident = parse_identificacao(sections.get("identificacao", ""))
    nome = known.get("nome") or ident.get("nome", f"Paciente {case_num}")
    idade = known.get("idade") or ident.get("idade", 0)
    sexo = known.get("sexo") or ident.get("sexo", "M")
    queixa = known.get("queixa_principal") or sections.get("queixa_principal", "")
    diagnostico = known.get("diagnostico_principal") or sections.get("diagnostico", "Nao especificado")

    case_data = {
        "identificacao": {
            "nome": nome, "idade": idade, "sexo": sexo,
            "cor": ident.get("cor"), "estado_civil": ident.get("estado_civil"),
            "profissao": ident.get("profissao"), "religiao": ident.get("religiao"),
            "residencia": ident.get("residencia"),
        },
        "queixa_principal_texto": queixa,
        "historia_doenca_atual": sections.get("historia_doenca_atual", ""),
        "interrogatorio_complementar": {"texto": sections.get("interrogatorio_complementar", "")},
        "historia_fisiologica": {"texto_livre": sections.get("historia_fisiologica", "")},
        "historia_patologica": {"doencas_previas": [], "cirurgias": [], "internacoes": [], "medicamentos_em_uso": [], "alergias": [], "texto_livre": sections.get("historia_patologica", "")},
        "historia_familiar": {"texto_livre": sections.get("historia_familiar", "")},
        "historia_social": {"texto_livre": sections.get("historia_social", "")},
        "exame_fisico": {"texto_livre": sections.get("exame_fisico", "")},
        "diagnostico_completo": sections.get("diagnostico", diagnostico),
        "hipoteses_diagnosticas": [],
        "raw_sections": sections,
    }

    # Query existing patient using ORM (avoids asyncpg enum codec issues)
    existing_result = await session.execute(
        select(VirtualPatient).where(VirtualPatient.case_number == case_num)
    )
    existing_patient = existing_result.scalar_one_or_none()

    if existing_patient:
        existing_patient.eixo_a = eixo_a
        existing_patient.eixo_b = eixo_b
        existing_patient.eixo_c = "baixo_letramento_vulneravel"
        existing_patient.complexidade = complexidade
        existing_patient.nome = nome
        existing_patient.idade = idade
        existing_patient.sexo = sexo
        existing_patient.queixa_principal = queixa
        existing_patient.diagnostico_principal = diagnostico
        existing_patient.case_data = case_data
        patient_id = existing_patient.id
        log.info(f"  Updated patient #{case_num} ({nome})")
    else:
        patient = VirtualPatient(
            case_number=case_num,
            eixo_a=eixo_a,
            eixo_b=eixo_b,
            eixo_c="baixo_letramento_vulneravel",
            complexidade=complexidade,
            nome=nome,
            idade=idade,
            sexo=sexo,
            queixa_principal=queixa,
            diagnostico_principal=diagnostico,
            case_data=case_data,
        )
        session.add(patient)
        await session.flush()
        patient_id = patient.id
        log.info(f"  Inserted patient #{case_num} ({nome}) — id={patient_id}")

    # Delete existing chunks for this patient
    await session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.patient_id == patient_id))

    log.info(f"  Building chunks from {len(sections)} sections: {list(sections.keys())[:5]}")
    all_chunks: list[tuple[str, str, int]] = []
    for section_name, section_text in sections.items():
        if not section_text.strip():
            continue
        for i, chunk in enumerate(chunk_text(section_text)):
            all_chunks.append((section_name, chunk, i))

    log.info(f"  Total chunks: {len(all_chunks)}")
    if not all_chunks:
        log.warning(f"  No chunks for case #{case_num} — committing patient only")
        await session.commit()
        return

    batch_size = 100
    for batch_start in range(0, len(all_chunks), batch_size):
        batch = all_chunks[batch_start:batch_start + batch_size]
        embeddings = await get_embeddings([c[1] for c in batch], api_key)
        for (section_name, chunk_content, chunk_index), embedding in zip(batch, embeddings):
            chunk = KnowledgeChunk(
                patient_id=patient_id,
                section=section_name,
                content=chunk_content,
                embedding=embedding,
                chunk_index=chunk_index,
                token_count=len(chunk_content.split()),
            )
            session.add(chunk)

    log.info(f"  Embedded {len(all_chunks)} chunks for case #{case_num}")
    await session.commit()


async def main(cases_dir: str, reset: bool = False) -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    cases_path = Path(cases_dir)
    docx_files = sorted(cases_path.glob("Caso_*.docx")) or sorted(cases_path.glob("Caso *.docx"))
    if not docx_files:
        log.error(f"No Caso_*.docx files found in {cases_dir}")
        sys.exit(1)
    log.info(f"Found {len(docx_files)} case files")
    if reset:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM knowledge_chunks"))
            await conn.execute(text("DELETE FROM virtual_patients"))
            log.info("Database reset")
    success = 0
    errors = 0
    for docx_path in docx_files:
        try:
            async with async_session() as session:
                await ingest_case(docx_path, session, OPENAI_API_KEY)
                success += 1
        except Exception as exc:
            log.error(f"FAILED {docx_path.name}: {exc}", exc_info=True)
            errors += 1
    await engine.dispose()
    log.info(f"Ingestion complete: {success} processed, {errors} errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest clinical case .docx files into pgvector")
    parser.add_argument("--cases-dir", default="data/cases")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.cases_dir, args.reset))
