"""Provedor OpenAI (chat completions via httpx, como no restante do projeto)."""
from __future__ import annotations

import os

import httpx

from app.modules.chat.llm.base import LLMError, LLMNotConfigured, LLMResult


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str) -> None:
        self.model = model

    async def chat(self, system, messages, max_tokens, temperature=0.7) -> LLMResult:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise LLMNotConfigured("OPENAI_API_KEY não configurada.")
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": self.model,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "messages": [{"role": "system", "content": system}, *messages],
                    },
                )
            resp.raise_for_status()
            data = resp.json()
            usage = data.get("usage") or {}
            return LLMResult(
                text=data["choices"][0]["message"]["content"] or "",
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
                model=data.get("model", self.model),
                provider=self.name,
            )
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise LLMError(f"OpenAI: {e.__class__.__name__}: {e}") from e
