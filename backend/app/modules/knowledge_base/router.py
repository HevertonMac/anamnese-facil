# backend/app/modules/knowledge_base/router.py
from __future__ import annotations
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models import KnowledgeChunk, VirtualPatient
from app.schemas.patient import (
    KnowledgeSearchRequest, KnowledgeSearchResult,
    VirtualPatientCreate, VirtualPatientDetail, VirtualPatientResponse,
)

router = APIRouter(prefix="/kb", tags=["knowledge_base"])


@router.get("/patients", response_model=list[VirtualPatientResponse])
async def list_patients(
    eixo_a: Optional[str] = Query(None),
    complexidade: Optional[str] = Query(None),
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    q = select(VirtualPatient)
    if active_only:
        q = q.where(VirtualPatient.is_active == True)
    if eixo_a:
        q = q.where(VirtualPatient.eixo_a == eixo_a)
    if complexidade:
        q = q.where(VirtualPatient.complexidade == complexidade)
    q = q.order_by(VirtualPatient.case_number)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/patients/{patient_id}", response_model=VirtualPatientDetail)
async def get_patient(patient_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VirtualPatient).where(VirtualPatient.id == patient_id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.post("/patients", response_model=VirtualPatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(data: VirtualPatientCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(VirtualPatient).where(VirtualPatient.case_number == data.case_number))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Case number {data.case_number} already exists")
    patient = VirtualPatient(**data.model_dump(exclude={"case_data"}), case_data=data.case_data.model_dump())
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    return patient


@router.post("/search", response_model=list[KnowledgeSearchResult])
async def semantic_search(req: KnowledgeSearchRequest, db: AsyncSession = Depends(get_db)):
    from app.core.embeddings import get_embedding

    query_embedding = await get_embedding(req.query)
    is_zero_vector = all(v == 0.0 for v in query_embedding)

    patient_filter = ""
    params: dict = {"top_k": req.top_k}
    if req.patient_id:
        patient_filter = "AND kc.patient_id = :patient_id"
        params["patient_id"] = str(req.patient_id)

    if is_zero_vector:
        # No API key — fall back to keyword search with ILIKE
        keyword = "%" + req.query.replace("%", "") + "%"
        params["keyword"] = keyword
        sql = text(f"""
            SELECT kc.patient_id, vp.nome AS patient_name, kc.section, kc.content,
                   0.5 AS similarity
            FROM knowledge_chunks kc
            JOIN virtual_patients vp ON vp.id = kc.patient_id
            WHERE kc.content ILIKE :keyword {patient_filter}
            ORDER BY kc.patient_id, kc.chunk_index
            LIMIT :top_k
        """)
    else:
        # Semantic search — CAST(:embedding AS vector) works with asyncpg
        embedding_str = "[" + ",".join(f"{v:.8f}" for v in query_embedding) + "]"
        params["embedding"] = embedding_str
        sql = text(f"""
            SELECT kc.patient_id, vp.nome AS patient_name, kc.section, kc.content,
                   1 - (kc.embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM knowledge_chunks kc
            JOIN virtual_patients vp ON vp.id = kc.patient_id
            WHERE kc.embedding IS NOT NULL {patient_filter}
            ORDER BY kc.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """)

    rows = await db.execute(sql, params)
    return [
        KnowledgeSearchResult(
            patient_id=row.patient_id, patient_name=row.patient_name,
            section=row.section, content=row.content, similarity=float(row.similarity),
        )
        for row in rows
    ]


@router.get("/stats")
async def knowledge_base_stats(db: AsyncSession = Depends(get_db)):
    patient_count = await db.scalar(select(func.count()).select_from(VirtualPatient))
    chunk_count = await db.scalar(select(func.count()).select_from(KnowledgeChunk))
    embedded_count = await db.scalar(
        select(func.count()).select_from(KnowledgeChunk).where(KnowledgeChunk.embedding.is_not(None))
    )
    by_area = await db.execute(
        select(VirtualPatient.eixo_a, func.count().label("count"))
        .group_by(VirtualPatient.eixo_a).order_by(VirtualPatient.eixo_a)
    )
    return {
        "total_patients": patient_count,
        "total_chunks": chunk_count,
        "embedded_chunks": embedded_count,
        "embedding_coverage": round(embedded_count / max(chunk_count, 1) * 100, 1),
        "by_clinical_area": {row.eixo_a: row.count for row in by_area},
    }


@router.post("/embed-all", tags=["knowledge_base"])
async def embed_all_chunks(
    batch_size: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Generates OpenAI embeddings for all knowledge_chunks with embedding IS NULL.
    Call once after populating the database. Returns a progress summary.
    """
    from app.core.embeddings import get_embeddings_batch

    # Fetch all chunks without embeddings
    result = await db.execute(
        select(KnowledgeChunk.id, KnowledgeChunk.content)
        .where(KnowledgeChunk.embedding.is_(None))
        .order_by(KnowledgeChunk.id)
    )
    rows = result.all()

    if not rows:
        return {"message": "All chunks already have embeddings.", "updated": 0}

    total = len(rows)
    updated = 0
    errors = 0

    for i in range(0, total, batch_size):
        batch = rows[i : i + batch_size]
        ids = [r.id for r in batch]
        texts = [r.content for r in batch]

        try:
            embeddings = await get_embeddings_batch(texts)
        except Exception as e:
            errors += len(batch)
            continue

        for chunk_id, emb in zip(ids, embeddings):
            vec_str = "[" + ",".join(f"{v:.8f}" for v in emb) + "]"
            await db.execute(
                text(
                    "UPDATE knowledge_chunks SET embedding = CAST(:emb AS vector) WHERE id = :id"
                ),
                {"emb": vec_str, "id": str(chunk_id)},
            )
        await db.commit()
        updated += len(batch)

    return {
        "message": "Done",
        "total_without_embedding": total,
        "updated": updated,
        "errors": errors,
    }


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def trigger_ingestion(cases_dir: str = "/app/data/cases", reset: bool = False):
    from app.core.tasks import ingest_cases_task
    task = ingest_cases_task.delay(cases_dir=cases_dir, reset=reset)
    return {"task_id": task.id, "status": "queued"}
