# Guia de Deploy Gratuito — Anamnese Fácil

Stack: **Supabase** (banco) + **Render** (backend) + **Vercel** (frontend)

---

## ⚠️ Antes de começar

Rotacione a `OPENAI_API_KEY` se ela foi exposta em logs ou conversas:
→ https://platform.openai.com/api-keys

---

## Passo 1 — Banco de dados: Supabase (grátis, pgvector incluso)

1. Crie uma conta em https://supabase.com
2. Clique em **New project** → preencha nome, senha (anote!) e região (preferencialmente US East)
3. Aguarde o projeto inicializar (~2 min)
4. Vá em **Project Settings → Database → Connection string**
5. Escolha **URI** e copie a string no formato:
   ```
   postgresql://postgres.[ref]:[SENHA]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```
6. **Substitua** `postgresql://` por `postgresql+asyncpg://` e copie para usar no Render

> O Supabase já tem a extensão `pgvector` disponível — o app a ativa automaticamente no startup.

---

## Passo 2 — Backend: Render (free tier)

1. Crie uma conta em https://render.com e conecte sua conta GitHub
2. Clique em **New → Web Service**
3. Selecione o repositório `HevertonMac/anamnese-facil`
4. Render detectará o `render.yaml` automaticamente
5. Preencha as variáveis de ambiente:

   | Variável | Valor |
   |---|---|
   | `DATABASE_URL` | String do Supabase (passo 1) com `postgresql+asyncpg://` |
   | `OPENAI_API_KEY` | Sua nova chave da OpenAI |
   | `ALLOWED_ORIGINS` | `https://anamnese-facil.vercel.app,http://localhost:3000` |

6. Clique em **Create Web Service**
7. Aguarde o build (~5 min). A URL será algo como `https://anamnese-facil-api.onrender.com`
8. Teste: acesse `https://anamnese-facil-api.onrender.com/health` → deve retornar `{"status":"ok"}`
9. Acesse `https://anamnese-facil-api.onrender.com/docs` para ver a documentação interativa da API

> **Nota:** O free tier do Render "dorme" após 15 min de inatividade. A primeira requisição pode levar ~30s para acordar.

---

## Passo 3 — Frontend: Vercel (grátis)

1. Crie uma conta em https://vercel.com e conecte sua conta GitHub
2. Clique em **New Project** → importe `HevertonMac/anamnese-facil`
3. Configure:
   - **Root Directory:** `frontend`
   - **Framework Preset:** Vite
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
4. Em **Environment Variables**, adicione:
   - `VITE_API_URL` = (deixe **vazio** — o `vercel.json` já faz o proxy para o Render)
5. Clique em **Deploy**
6. A URL será algo como `https://anamnese-facil.vercel.app`

---

## Passo 4 — Atualizar CORS no Render

Após obter a URL do Vercel:

1. Vá no serviço no Render → **Environment**
2. Atualize `ALLOWED_ORIGINS` com a URL real do Vercel:
   ```
   https://anamnese-facil.vercel.app,http://localhost:3000
   ```
3. Render fará redeploy automático

---

## Passo 5 (opcional) — Ingestão dos casos clínicos

Para popular o banco com os 10 casos já existentes:

```bash
# Configure o .env local apontando para o Supabase
DATABASE_URL=postgresql+asyncpg://... python -m backend.scripts.ingest.ingest_cases
```

Ou use a API diretamente via `/docs` após o deploy.

---

## URLs finais esperadas

| Serviço | URL |
|---|---|
| Frontend | `https://anamnese-facil.vercel.app` |
| API (docs interativos) | `https://anamnese-facil-api.onrender.com/docs` |
| Health check | `https://anamnese-facil-api.onrender.com/health` |

---

## Atualizar o vercel.json

Após criar o serviço no Render, abra `frontend/vercel.json` e substitua
`anamnese-facil-api.onrender.com` pela URL real gerada pelo Render (se for diferente).

Então faça commit e push — o Vercel redeploya automaticamente.
