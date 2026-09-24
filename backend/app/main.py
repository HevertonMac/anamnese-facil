# backend/app/main.py
from __future__ import annotations
import logging, os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import engine
from app.db.models import Base
from app.modules.knowledge_base.router import router as kb_router
from app.modules.patient.router import router as patient_router

log = logging.getLogger(__name__)

app = FastAPI(
    title="Anamnese Fácil API",
    description="Plataforma de anamnese com pacientes virtuais — PPGCC/UFPI",
    version="0.1.0",
)

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(kb_router, prefix="/api/v1")
app.include_router(patient_router, prefix="/api/v1")


@app.on_event("startup")
async def on_startup() -> None:
    import re
    from sqlalchemy import text
    db_url = os.environ.get("DATABASE_URL", "not set")
    db_host = re.search(r'@([^:/]+)', db_url)
    log.warning(f"[DB] Connecting to host: {db_host.group(1) if db_host else 'unknown'}")
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
        log.warning("[DB] Database tables ready — startup OK")
    except Exception as e:
        log.error(f"[DB] Startup connection failed: {e.__class__.__name__}: {e}")
        log.error("[DB] Service running WITHOUT database — endpoints may fail")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "anamnese-facil-api"}
