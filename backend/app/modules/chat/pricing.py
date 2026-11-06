"""Preços por 1M de tokens (USD) e cálculo de custo.

Os valores padrão são apenas referência e PODEM estar desatualizados: confirme nas páginas
oficiais de preço de cada provedor. Sobrescreva/complete via CHAT_PRICES_JSON, ex.:
    CHAT_PRICES_JSON='{"anthropic:claude-haiku-5-5": [1.0, 5.0]}'   # [entrada, saída]
Modelos sem preço conhecido têm custo registrado como 0 (e um aviso no log).
"""
from __future__ import annotations

import json
import logging
import os
from decimal import Decimal

log = logging.getLogger(__name__)

DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    "openai:gpt-4o-mini": (0.15, 0.60),
    "openai:gpt-4o": (2.50, 10.00),
}


def load_prices() -> dict[str, tuple[float, float]]:
    prices = dict(DEFAULT_PRICES)
    raw = os.environ.get("CHAT_PRICES_JSON", "")
    if raw:
        try:
            for key, (p_in, p_out) in json.loads(raw).items():
                prices[key] = (float(p_in), float(p_out))
        except (ValueError, TypeError) as e:
            log.error(f"CHAT_PRICES_JSON inválido, ignorado: {e}")
    return prices


def lookup_price(provider: str, model: str) -> tuple[float, float] | None:
    prices = load_prices()
    if f"{provider}:{model}" in prices:
        return prices[f"{provider}:{model}"]
    # o provedor devolve ids datados (ex.: gpt-4o-mini-2024-07-18): casa pelo prefixo mais longo
    matches = [k for k in prices if k.startswith(f"{provider}:") and model.startswith(k.split(":", 1)[1])]
    return prices[max(matches, key=len)] if matches else None


def cost_usd(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
    price = lookup_price(provider, model)
    if price is None:
        log.warning(f"Sem preço para {provider}:{model}; custo registrado como 0. Defina CHAT_PRICES_JSON.")
        return Decimal(0)
    p_in, p_out = price
    return (Decimal(str(p_in)) * prompt_tokens + Decimal(str(p_out)) * completion_tokens) / Decimal(1_000_000)
