"""Projeta o custo do chatbot por sessão / aluno / mês (offline, sem chamar API).

Modelo: a cada turno o provedor recebe system prompt + histórico (janela) + nova fala do aluno, então o
custo de ENTRADA cresce com o turno; a SAÍDA é a resposta do paciente.

Exemplos:
    python -m scripts.estimate_chat_cost --students 100 --sessions-per-student-month 8 --turns 15
    python -m scripts.estimate_chat_cost --case-file caso.json --price anthropic:claude-haiku-5-5=1,5
Preços (USD por 1M tokens, entrada,saída): padrão em app/modules/chat/pricing.py; confirme os vigentes
nas páginas oficiais dos provedores e informe-os com --price quando faltarem.
"""
from __future__ import annotations

import argparse
import json
import sys

from app.modules.chat.pricing import load_prices
from app.modules.chat.prompt import build_system_prompt


def est_tokens(text: str) -> int:
    """Aproximação ~4 caracteres por token (português tende a ficar um pouco acima)."""
    return max(1, round(len(text) / 4))


def session_tokens(system_tokens: int, turns: int, user_tok: int, reply_tok: int, window: int) -> tuple[int, int]:
    """Retorna (tokens de entrada totais, tokens de saída totais) de uma sessão de `turns` turnos."""
    prompt_total = 0
    for t in range(turns):
        history_msgs = min(2 * t, window)  # mensagens anteriores reenviadas (aluno+paciente)
        history_tok = history_msgs * (user_tok + reply_tok) // 2
        prompt_total += system_tokens + history_tok + user_tok
    return prompt_total, turns * reply_tok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--students", type=int, default=100)
    ap.add_argument("--sessions-per-student-month", type=float, default=8)
    ap.add_argument("--turns", type=int, default=15, help="trocas aluno->paciente por sessão")
    ap.add_argument("--avg-user-tokens", type=int, default=25)
    ap.add_argument("--avg-reply-tokens", type=int, default=60)
    ap.add_argument("--history-window", type=int, default=20, help="CHAT_MAX_HISTORY (mensagens reenviadas)")
    ap.add_argument("--system-prompt-tokens", type=int, default=None, help="padrão: mede --case-file ou usa 1500")
    ap.add_argument("--case-file", help="JSON com case_data de um paciente para medir o system prompt")
    ap.add_argument("--price", action="append", default=[], metavar="PROV:MODELO=ENTRADA,SAIDA")
    args = ap.parse_args(argv)

    if args.system_prompt_tokens is not None:
        system_tok = args.system_prompt_tokens
    elif args.case_file:
        with open(args.case_file, encoding="utf-8") as f:
            system_tok = est_tokens(build_system_prompt(json.load(f)))
    else:
        system_tok = 1500

    prices = load_prices()
    for p in args.price:
        key, _, val = p.partition("=")
        p_in, _, p_out = val.partition(",")
        prices[key] = (float(p_in), float(p_out))

    prompt_tok, out_tok = session_tokens(system_tok, args.turns, args.avg_user_tokens, args.avg_reply_tokens, args.history_window)
    sessions_month = args.students * args.sessions_per_student_month

    print(f"System prompt: ~{system_tok} tok | {args.turns} turnos/sessão | janela {args.history_window} msgs")
    print(f"Por sessão: {prompt_tok} tok entrada + {out_tok} tok saída")
    print(f"Sessões/mês: {sessions_month:.0f} ({args.students} alunos x {args.sessions_per_student_month:g})\n")
    print(f"{'modelo':<36}{'USD/sessão':>12}{'USD/aluno/mês':>16}{'USD/mês':>12}")
    for key, (p_in, p_out) in sorted(prices.items()):
        per_session = (prompt_tok * p_in + out_tok * p_out) / 1_000_000
        print(f"{key:<36}{per_session:>12.4f}{per_session * args.sessions_per_student_month:>16.3f}{per_session * sessions_month:>12.2f}")
    print("\nObs.: estimativa sem cache de prompt; tokens aproximados (chars/4). Compare com /chat/usage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
