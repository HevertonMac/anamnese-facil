"""
Script para criar (ou atualizar) um usuário administrador no banco.

Uso:
    python scripts/create_admin.py

Variáveis de ambiente necessárias (lidas do .env na raiz do projeto ou do ambiente):
    DATABASE_URL   — ex: postgresql+asyncpg://...
    ADMIN_EMAIL    — e-mail do admin (padrão: heverton.macedo@ufpi.edu.br)
    ADMIN_NAME     — nome completo (padrão: Heverton Macedo)
    ADMIN_PASSWORD — senha em texto puro (obrigatória)
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Adiciona o diretório pai (backend/) ao path para importar os módulos da app
sys.path.insert(0, str(Path(__file__).parent.parent))

# Carrega .env da raiz do projeto (opcional — ignora se não existir)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv não instalado; usa variáveis de ambiente do sistema

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, User
from app.modules.auth.service import get_password_hash

DATABASE_URL = os.environ["DATABASE_URL"]
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "heverton.macedo@ufpi.edu.br")
ADMIN_NAME = os.environ.get("ADMIN_NAME", "Heverton Macedo")
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as db:
        result = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        user: User | None = result.scalar_one_or_none()

        if user:
            user.hashed_password = get_password_hash(ADMIN_PASSWORD)
            user.role = "admin"
            user.full_name = ADMIN_NAME
            user.is_active = True
            print(f"✅ Usuário atualizado: {ADMIN_EMAIL} (role=admin)")
        else:
            user = User(
                email=ADMIN_EMAIL,
                hashed_password=get_password_hash(ADMIN_PASSWORD),
                full_name=ADMIN_NAME,
                role="admin",
                is_active=True,
            )
            db.add(user)
            print(f"✅ Usuário criado: {ADMIN_EMAIL} (role=admin)")

        await db.commit()

    await engine.dispose()
    print("✔ Concluído.")


if __name__ == "__main__":
    if not ADMIN_PASSWORD:
        print("❌ Defina a variável ADMIN_PASSWORD antes de rodar o script.")
        sys.exit(1)
    asyncio.run(main())
