from __future__ import annotations

from app.modules.chat import config
from app.modules.chat.llm.anthropic_provider import AnthropicProvider
from app.modules.chat.llm.base import LLMError, LLMProvider
from app.modules.chat.llm.openai_provider import OpenAIProvider

_PROVIDERS = {"openai": OpenAIProvider, "anthropic": AnthropicProvider}


def get_provider() -> LLMProvider:
    name = config.provider_name()
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise LLMError(f"CHAT_PROVIDER inválido: {name!r} (use: {', '.join(_PROVIDERS)})")
    return cls(config.model_name(name))
