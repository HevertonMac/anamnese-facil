# Anamnese Fácil

Plataforma baseada em IA para geração de pacientes virtuais e avaliação automatizada da anamnese médica.

## Visão Geral

Desenvolvida como parte do PPGCC/UFPI, a plataforma integra LLMs, RAG e NLU para:
- Gerar perfis de pacientes virtuais clinicamente coerentes
- Simular entrevistas de anamnese em linguagem natural
- Avaliar automaticamente a qualidade das anamneses com feedback formativo

## Estrutura do Projeto

```
anamnese-facil/
├── backend/          # FastAPI + Python
│   ├── app/
│   │   ├── modules/  # Módulos de domínio (auth, patient, simulation, evaluation, dashboard)
│   │   ├── core/     # Configurações, segurança, dependências
│   │   ├── db/       # Modelos SQLAlchemy e sessão do banco
│   │   └── schemas/  # Schemas Pydantic
│   ├── scripts/
│   │   └── ingest/   # Pipeline de ingestão da base de conhecimento
│   └── tests/
├── frontend/         # React + TypeScript + Vite
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── store/
│       ├── hooks/
│       └── services/
├── docker/           # Dockerfiles e configurações
├── docs/             # Documentação técnica e de API
└── scripts/          # Scripts utilitários
```

## Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy, Celery
- **Frontend**: React 18, TypeScript, TailwindCSS, shadcn/ui
- **IA/RAG**: LangChain, OpenAI GPT-4o / Anthropic Claude
- **Banco de dados**: PostgreSQL 16 + pgvector, Redis
- **Infra**: Docker, Docker Compose, Nginx, GitHub Actions

## Início Rápido

```bash
# Clone o repositório
git clone https://github.com/<seu-usuario>/anamnese-facil.git
cd anamnese-facil

# Configure as variáveis de ambiente
cp .env.example .env
# Edite .env com suas chaves de API

# Suba os serviços
docker compose up -d
```

## Autor

Heverton Kenedy Alves Costa Macêdo — heverton.macedo@ufpi.edu.br  
PPGCC / UFPI
