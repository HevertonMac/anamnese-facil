from __future__ import annotations

from app.modules.chat import config
from app.modules.chat.llm.anthropic_provider import AnthropicProvider
from app.modules.chat.llm.base import LLMError, LLMProvider
from app.modules.chat.llm.openai_provider import OpenAIProvider

_PROVIDERS = {"openai": OpenAIProvider, "anthropic": AnthropicProvider}


def get_provider(provider: str | None = None, model: str | None = None) -> LLMProvider:
    """Provedor/modelo da sessão; sem argumentos usa o padrão do ambiente."""
    name = (provider or config.provider_name()).lower()
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise LLMError(f"CHAT_PROVIDER inválido: {name!r} (use: {', '.join(_PROVIDERS)})")
    return cls(model or config.model_name(name))
