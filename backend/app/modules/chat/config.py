"""Configuração do chat lida do ambiente a cada chamada (facilita testes e troca a quente)."""
from __future__ import annotations

import os

DEFAULT_MODELS = {"openai": "gpt-4o-mini", "anthropic": "claude-haiku-5-5"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def provider_name() -> str:
    return os.environ.get("CHAT_PROVIDER", "openai").strip().lower()


def model_name(provider: str | None = None) -> str:
    provider = provider or provider_name()
    return os.environ.get("CHAT_MODEL") or DEFAULT_MODELS.get(provider, "")


def max_history() -> int:
    return _int("CHAT_MAX_HISTORY", 20)


def max_output_tokens() -> int:
    return _int("CHAT_MAX_OUTPUT_TOKENS", 300)


def max_messages_per_session() -> int:
    return _int("CHAT_MAX_MESSAGES_PER_SESSION", 60)


def max_message_chars() -> int:
    return _int("CHAT_MAX_MESSAGE_CHARS", 1000)


def rate_limit_per_minute() -> int:
    return _int("CHAT_RATE_LIMIT_PER_MIN", 20)
