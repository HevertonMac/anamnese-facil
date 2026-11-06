# Chatbot do paciente — custos

## Como o custo é gerado
A cada mensagem do aluno o backend envia ao LLM: **system prompt** (regras + `case_data` do paciente) +
**últimas `CHAT_MAX_HISTORY` mensagens** + a nova fala. Logo, a entrada cresce a cada turno; a saída é
limitada por `CHAT_MAX_OUTPUT_TOKENS`. Cada resposta do paciente grava `prompt_tokens`, `completion_tokens`,
`model`, `provider` e `cost_usd` em `conversation_messages`.

## Medir (custo real)
- Admin: `GET /api/v1/chat/usage?days=30` (agregado por dia/usuário/modelo). Na tela de chat, admins veem
  tokens e custo por mensagem e da sessão.
- Preços em `app/modules/chat/pricing.py` (apenas referência) ou `CHAT_PRICES_JSON`. **Confirme os valores
  vigentes nas páginas oficiais**; modelos sem preço registram custo 0 com aviso no log.

## Registros para análise
- Por mensagem (`conversation_messages`): tokens de entrada/saída, modelo, provedor, `cost_usd` e `latency_ms`.
- Por sessão (admin): `GET /api/v1/chat/usage/sessions?days=30` (JSON) ou `/usage/sessions.csv` (planilha):
  aluno, caso, turnos, tokens, custo, latência média, status e horários. Dá para calcular custo médio por
  sessão/turno e comparar provedores e modelos.

## Análise de custos na plataforma (somente dev)
- Tela **Custos (dev)** (`/custos`, só admin): *Painel* (totais, custo por dia, por modelo, por caso e por aluno,
  custo por sessão/turno, tokens médios, latência média e p95), *Conversas* (lista filtrável por modelo/e-mail
  com transcrição, tokens/custo/latência por mensagem e o system prompt usado) e *Modelos* (comparação lado a lado).
  Exporta CSV (sessões) e JSON (conversas completas).
- Exclusividade: controlada por `CHAT_ANALYTICS_ENABLED`; se ausente, liga só com `ENVIRONMENT=development`.
  Desligada, os endpoints `/chat/usage*` e `/chat/analytics/*` respondem 404 e o menu some. O `render.yaml`
  fixa `false` em produção.
- Cada sessão guarda provedor, modelo, temperatura e o system prompt (congelado na criação), então a conversa
  é reproduzível e comparável mesmo se o caso for editado depois.

## Escolha do modelo
Admin escolhe o modelo da OpenAI ao iniciar a conversa (lista em `CHAT_ALLOWED_MODELS`, default
`gpt-4o-mini,gpt-4o`). Alunos usam `CHAT_MODEL`. Preços de modelos novos: `CHAT_PRICES_JSON`.

## Projetar (simulador)
```
cd backend
python -m scripts.estimate_chat_cost --students 100 --sessions-per-student-month 8 --turns 15 \
    --case-file caso.json --price anthropic:claude-haiku-5-5=<entrada>,<saida>
```
Fórmula por sessão: `Σ_t (system + min(2t, janela)·tokens_médios_msg + fala_aluno)` de entrada +
`turnos · resposta` de saída. Tokens aproximados por caracteres/4 (sem cache de prompt).

## Alavancas de custo
`CHAT_MODEL` mais barato, janela menor (`CHAT_MAX_HISTORY`), system prompt enxuto, `CHAT_MAX_OUTPUT_TOKENS`,
limite de mensagens por sessão e rate limit por aluno. Cache de prompt do provedor pode reduzir a entrada
repetida (não implementado).

## Migração
As novas colunas de `conversation_messages` exigem `alembic upgrade head` (0003); `create_all` não altera tabelas existentes.
