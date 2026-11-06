"""Interface comum dos provedores de LLM usados pelo chat."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LLMError(Exception):
    """Falha ao chamar o provedor (rede, HTTP != 2xx ou resposta malformada)."""


class LLMNotConfigured(LLMError):
    """Chave de API do provedor ausente."""


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    provider: str


class LLMProvider(Protocol):
    name: str
    model: str

    async def chat(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float = 0.7,
    ) -> LLMResult: ...
