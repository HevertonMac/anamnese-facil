#!/usr/bin/env python3
"""
backend/scripts/ingest/ingest_cases.py
---------------------------------------
Ingestion pipeline: DOCX clinical cases -> structured JSON -> pgvector

O parsing/estruturação está em `case_parser.py` e `case_structure.py` (funções puras, testadas em
`tests/test_case_parser.py`). Este arquivo cuida da curadoria (KNOWN_CASES), da gravação no banco
e dos embeddings.

Usage:
    python -m scripts.ingest.ingest_cases --cases-dir data/cases/ --dry-run        # só analisa
    python -m scripts.ingest.ingest_cases --cases-dir data/cases/ --only 40-60     # ingere um intervalo
    python -m scripts.ingest.ingest_cases --cases-dir data/cases/                  # todos (upsert por case_number)
    python -m scripts.ingest.ingest_cases --cases-dir data/cases/ --reset          # apaga tudo antes
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import httpx
from sqlalchemy import text, select, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.models import VirtualPatient, KnowledgeChunk
from scripts.ingest.case_parser import (
    SECTION_LABELS, chunk_text, infer_eixo_c, map_complexidade, map_eixo_a, map_eixo_b,
    norm, parse_case, quality_report, short_diagnosis,
)
from scripts.ingest.case_structure import build_case_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/anamnese_facil")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# Curadoria manual: tem prioridade sobre o que o parser extrai do documento (divergências são avisadas).
# Vazia: os casos 1-10 (modelo padronizado) vêm inteiramente do documento. Casos futuros só entram aqui se o documento não trouxer o dado.
KNOWN_CASES: dict[int, dict] = {
}

def docx_to_text(docx_path: Path) -> str:
    result = subprocess.run(
        ["pandoc", str(docx_path), "-t", "plain", "--wrap=none"],
        capture_output=True, text=True, check=True,
        encoding="utf-8",
    )
    return result.stdout


_GENERIC_DX_TOKENS = {"aguda", "agudo", "cronica", "cronico", "grave", "sindrome", "doenca", "forma", "provavel"}


def _agree(a: str, b: str) -> bool:
    """Dois diagnósticos 'concordam' se um contém o outro ou compartilham um termo clínico
    (comparando os 6 primeiros caracteres, o que tolera variações como 'Hepatoesplênica/Hepatoesplenica')."""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    if na in nb or nb in na:
        return True

    def stems(n: str) -> set[str]:
        return {t[:6] for t in n.split() if len(t) >= 6 and t not in _GENERIC_DX_TOKENS}

    return bool(stems(na) & stems(nb))


def resolve_classification(
    case_num: int, parsed: dict[str, Any], existing_eixo_c: Optional[str] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Decide os campos estruturados do paciente. Ordem: curadoria (KNOWN_CASES) > documento > padrão.
    Cada decisão registra a fonte; divergências entre curadoria e documento viram avisos.
    Retorna (classificacao, ident_final).
    """
    known = KNOWN_CASES.get(case_num, {})
    meta = parsed["metadados"]
    ident = dict(parsed["identificacao"])
    avisos: list[str] = []
    divergencias: list[str] = []
    fontes: dict[str, str] = {}

    def choose(field: str, curated: Any, doc: Any, default: Any = None, doc_label: str = "documento") -> Any:
        if curated not in (None, ""):
            fontes[field] = "curadoria"
            # nome/queixa curados são formas curtas (primeiro nome, rótulo da queixa): só divergem
            # se não forem prefixo/trecho do que o documento traz.
            if doc not in (None, "") and doc != curated and field not in ("queixa_principal",)                     and not (field == "nome" and norm(str(doc)).startswith(norm(str(curated)))):
                divergencias.append(f"{field}: curadoria='{curated}' documento='{doc}'")
            return curated
        if doc not in (None, ""):
            fontes[field] = doc_label
            return doc
        fontes[field] = "padrao"
        avisos.append(f"{field} não encontrado no documento nem na curadoria; usado padrão '{default}'")
        return default

    eixo_a = choose("eixo_a", known.get("eixo_a"), map_eixo_a(meta.get("eixo_a_bruto", "")), "cardiovascular")
    eixo_b = choose("eixo_b", known.get("eixo_b"), map_eixo_b(meta.get("eixo_b_bruto", "")), "colaborativo")
    complexidade = choose("complexidade", known.get("complexidade"), map_complexidade(meta.get("complexidade_bruta", "")), "media")

    eixo_c_doc, eixo_c_src = infer_eixo_c(meta.get("eixo_c_bruto", ""), ident.get("idade_meses"), ident.get("escolaridade", ""))
    if eixo_c_doc:
        eixo_c, fontes["eixo_c"] = eixo_c_doc, f"documento:{eixo_c_src}"
    elif existing_eixo_c:
        eixo_c, fontes["eixo_c"] = existing_eixo_c, "banco(anterior)"
        avisos.append("eixo_c indeterminado no documento; mantido valor anterior do banco")
    else:
        eixo_c, fontes["eixo_c"] = "medio_letramento_media", "padrao"
        avisos.append("eixo_c indeterminado; usado padrão 'medio_letramento_media' — revisar")

    nome = choose("nome", known.get("nome"), ident.get("nome"), f"Paciente {case_num}")
    idade = choose("idade", known.get("idade"), ident.get("idade"), 0)
    sexo = choose("sexo", known.get("sexo"), ident.get("sexo"), "M")
    ident.update({"nome": nome, "idade": idade, "sexo": sexo})

    queixa_doc = parsed["sections"].get("queixa_principal", "") or meta.get("queixa_bruta", "")
    queixa_doc = (queixa_doc.split("\n\n")[0] if queixa_doc else "").strip()
    queixa = choose("queixa_principal", known.get("queixa_principal"), queixa_doc, "")

    dx_doc = parsed["diagnostico"]
    dx_curado = known.get("diagnostico_principal")
    if dx_doc and dx_curado:
        fontes["diagnostico_principal"] = "curadoria+" + dx_doc["fonte"]
        if not _agree(dx_curado, dx_doc["principal"]):
            divergencias.append(f"diagnostico_principal: curadoria='{dx_curado}' documento='{dx_doc['principal'][:90]}'")
        diagnostico = dx_curado
    elif dx_curado:
        fontes["diagnostico_principal"] = "curadoria"
        avisos.append("documento não traz diagnóstico explícito; diagnóstico vem da curadoria — revisar clinicamente")
        diagnostico = dx_curado
    elif dx_doc:
        fontes["diagnostico_principal"] = dx_doc["fonte"]
        diagnostico = short_diagnosis(dx_doc["principal"])
        if dx_doc["fonte"] == "documento:eixo_a" and not meta.get("eixo_b_nuance") and "eixo_c_letramento" not in meta:
            # No modelo E (padronizado) o diagnóstico vive no Eixo A por desenho; só avisa nos modelos antigos.
            avisos.append("diagnóstico extraído do texto do Eixo A (sem seção de diagnóstico) — confirmar")
    else:
        fontes["diagnostico_principal"] = "ausente"
        avisos.append("diagnóstico ausente")
        diagnostico = "Não especificado"

    classificacao = {
        "eixo_a": eixo_a, "eixo_b": eixo_b, "eixo_c": eixo_c, "complexidade": complexidade,
        "nome": nome, "idade": idade, "sexo": sexo, "queixa_principal": queixa,
        "diagnostico_principal": diagnostico,
        "diagnostico_principal_curto": truncate(diagnostico),
        "diagnostico_curado": dx_curado,
        # Detalhes do modelo E (ausentes nos modelos antigos): o enum eixo_c não os distingue, então ficam aqui.
        "letramento": meta.get("eixo_c_letramento"),
        "condicao_social": meta.get("eixo_c_condicao_social"),
        "perfil_sociodemografico": meta.get("eixo_c_descricao"),
        "nuance_eixo_b": meta.get("eixo_b_nuance"),
        "fontes": fontes, "avisos": avisos, "divergencias": divergencias,
    }
    return classificacao, ident


def truncate(value: str, limit: int = 200) -> str:
    value = value.strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def prepare_case(docx_path: Path, existing_eixo_c: Optional[str] = None) -> dict[str, Any]:
    """Lê o .docx e devolve tudo o que será gravado (sem tocar no banco)."""
    raw_text = docx_to_text(docx_path)
    m = re.search(r"Caso[_\s]?(\d+)", docx_path.stem, re.I)
    if not m:
        raise ValueError(f"não foi possível determinar o número do caso em '{docx_path.name}'")
    case_num = int(m.group(1))  # o nome do arquivo é a fonte canônica do número

    parsed = parse_case(raw_text)
    classificacao, ident = resolve_classification(case_num, parsed, existing_eixo_c)
    qualidade = quality_report(parsed)
    doc_num = parsed["metadados"].get("numero_no_documento")
    if doc_num and doc_num != case_num:
        qualidade["avisos"].append(f"arquivo é o caso {case_num}, mas o conteúdo diz caso {doc_num} — usado o do arquivo")
    qualidade["avisos"].extend(classificacao["avisos"])
    qualidade["divergencias"] = classificacao["divergencias"]
    qualidade["revisao_necessaria"] = bool(
        classificacao["divergencias"]
        or any(classificacao["fontes"].get(f) == "padrao" for f in ("eixo_a", "eixo_b", "complexidade", "eixo_c"))
        or classificacao["fontes"].get("diagnostico_principal") in ("curadoria", "ausente")
        or any("diagnóstico extraído do texto do Eixo A" in a for a in qualidade["avisos"])
        or any("obrigatória" in a for a in qualidade["avisos"])
    )
    case_data = build_case_data(
        parsed, ident_final=ident, classificacao=classificacao,
        qualidade=qualidade, arquivo=docx_path.name,
    )
    return {"case_num": case_num, "parsed": parsed, "classificacao": classificacao,
            "qualidade": qualidade, "case_data": case_data}


def build_chunks(case_num: int, nome: str, parsed: dict[str, Any]) -> list[tuple[str, str, int]]:
    """(seção, conteúdo, índice). Interrogatório e exame físico são divididos por sistema/aparelho."""
    chunks: list[tuple[str, str, int]] = []
    for section, text in parsed["sections"].items():
        if not text.strip():
            continue
        if section in ("interrogatorio_complementar", "exame_fisico"):
            blocks = parsed["interrogatorio"] if section == "interrogatorio_complementar" else parsed["exame_fisico_blocos"]
            pieces = [text] if set(blocks) <= {"_introducao"} else [
                (v if k == "_introducao" else f"{k}: {v}") for k, v in blocks.items()
            ]
        else:
            pieces = [text]
        parts: list[str] = []
        for piece in pieces:
            parts.extend(chunk_text(piece))
        chunks.extend((section, part, i) for i, part in enumerate(parts))
    return chunks


def embedding_input(case_num: int, nome: str, section: str, content: str) -> str:
    """Contexto usado só no embedding (não é gravado): ajuda a busca a distinguir seção e caso."""
    return f"Caso {case_num} — {nome} — {SECTION_LABELS.get(section, section)}\n{content}"


async def get_embeddings(texts: list[str], api_key: str) -> list[list[float]]:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": EMBEDDING_MODEL, "input": texts},
            timeout=60.0,
        )
        resp.raise_for_status()
        data = sorted(resp.json()["data"], key=lambda item: item["index"])
        if len(data) != len(texts):
            raise RuntimeError(f"embeddings: esperado {len(texts)}, recebido {len(data)}")
        return [item["embedding"] for item in data]


async def ingest_case(docx_path: Path, session: AsyncSession, api_key: str) -> dict[str, Any]:
    log.info(f"Processing: {docx_path.name}")
    m = re.search(r"Caso[_\s]?(\d+)", docx_path.stem, re.I)
    existing = None
    if m:
        existing = (await session.execute(
            select(VirtualPatient).where(VirtualPatient.case_number == int(m.group(1)))
        )).scalar_one_or_none()
    prepared = prepare_case(docx_path, existing_eixo_c=str(getattr(existing.eixo_c, "value", existing.eixo_c)) if existing else None)
    case_num, parsed, c = prepared["case_num"], prepared["parsed"], prepared["classificacao"]

    for aviso in prepared["qualidade"]["avisos"]:
        log.warning(f"  caso {case_num}: {aviso}")

    fields = dict(
        eixo_a=c["eixo_a"], eixo_b=c["eixo_b"], eixo_c=c["eixo_c"], complexidade=c["complexidade"],
        nome=c["nome"], idade=c["idade"], sexo=c["sexo"], queixa_principal=c["queixa_principal"],
        diagnostico_principal=c["diagnostico_principal_curto"], case_data=prepared["case_data"],
    )
    if existing:
        for key, value in fields.items():
            setattr(existing, key, value)
        patient_id = existing.id
        log.info(f"  Updated patient #{case_num} ({c['nome']})")
    else:
        patient = VirtualPatient(case_number=case_num, **fields)
        session.add(patient)
        await session.flush()
        patient_id = patient.id
        log.info(f"  Inserted patient #{case_num} ({c['nome']}) — id={patient_id}")

    await session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.patient_id == patient_id))

    chunks = build_chunks(case_num, c["nome"], parsed)
    log.info(f"  Total chunks: {len(chunks)} ({len(parsed['sections'])} seções)")
    for start in range(0, len(chunks), 100):
        batch = chunks[start:start + 100]
        embeddings = await get_embeddings(
            [embedding_input(case_num, c["nome"], s, t) for s, t, _ in batch], api_key)
        for (section, content, index), embedding in zip(batch, embeddings):
            session.add(KnowledgeChunk(
                patient_id=patient_id, section=section, content=content,
                embedding=embedding, chunk_index=index, token_count=len(content.split()),
            ))
    await session.commit()  # paciente + chunks gravados juntos (ou nada, se algo falhar acima)
    return prepared


def parse_case_selection(spec: str) -> set[int]:
    """'40-60' | '5,7,40-42' -> {números}."""
    numbers: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            numbers.update(range(int(a), int(b) + 1))
        else:
            numbers.add(int(part))
    return numbers


def find_case_files(cases_dir: Path, only: Optional[set[int]] = None) -> list[Path]:
    files: dict[int, Path] = {}
    for f in list(cases_dir.glob("Caso_*.docx")) + list(cases_dir.glob("Caso [0-9]*.docx")):
        m = re.search(r"(\d+)", f.stem)
        if not m:
            continue
        n = int(m.group(1))
        if only is not None and n not in only:
            continue
        if n in files:
            log.warning(f"Mais de um arquivo para o caso {n}: '{files[n].name}' e '{f.name}' — usando '{f.name}'")
        files[n] = f
    return [files[n] for n in sorted(files)]


def print_dry_run(prepared: dict[str, Any]) -> None:
    c, q = prepared["classificacao"], prepared["qualidade"]
    print(f"#{prepared['case_num']:>2} {c['nome'][:32]:<32} {c['idade']:>3}a {c['sexo']} | "
          f"{c['eixo_a']:<20} {c['eixo_b']:<12} {c['eixo_c']:<28} {c['complexidade']:<5} | "
          f"{c['diagnostico_principal_curto'][:48]} [{c['fontes'].get('diagnostico_principal')}]")
    for key in ("divergencias", "avisos"):
        for item in q.get(key, []):
            print(f"      {'≠' if key == 'divergencias' else '!'} {item}")


async def main(cases_dir: str, reset: bool = False, only: Optional[set[int]] = None, dry_run: bool = False) -> None:
    docx_files = find_case_files(Path(cases_dir), only)
    if not docx_files:
        log.error(f"Nenhum arquivo de caso encontrado em {cases_dir}" + (f" para {sorted(only)}" if only else ""))
        sys.exit(1)
    log.info(f"Found {len(docx_files)} case files")

    if dry_run:
        for docx_path in docx_files:
            print_dry_run(prepare_case(docx_path))
        return

    if not OPENAI_API_KEY:
        log.error("OPENAI_API_KEY não definida — sem embeddings reais a busca semântica ficaria incorreta. Abortando.")
        sys.exit(1)

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    if reset:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM knowledge_chunks"))
            await conn.execute(text("DELETE FROM virtual_patients"))
            log.info("Database reset")
    success = errors = needs_review = 0
    for docx_path in docx_files:
        try:
            async with async_session() as session:
                prepared = await ingest_case(docx_path, session, OPENAI_API_KEY)
                success += 1
                needs_review += bool(prepared["qualidade"]["revisao_necessaria"])
        except Exception as exc:
            log.error(f"FAILED {docx_path.name}: {exc}", exc_info=True)
            errors += 1
    await engine.dispose()
    log.info(f"Ingestion complete: {success} processed, {errors} errors, {needs_review} com revisão necessária")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest clinical case .docx files into pgvector")
    parser.add_argument("--cases-dir", default="data/cases")
    parser.add_argument("--only", help="casos a processar, ex.: 40-60 ou 5,7,40-42 (padrão: todos)")
    parser.add_argument("--dry-run", action="store_true", help="só analisa os documentos e mostra o resultado; não acessa o banco")
    parser.add_argument("--reset", action="store_true", help="apaga TODOS os pacientes/chunks antes de ingerir")
    args = parser.parse_args()
    asyncio.run(main(args.cases_dir, args.reset, parse_case_selection(args.only) if args.only else None, args.dry_run))
