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
