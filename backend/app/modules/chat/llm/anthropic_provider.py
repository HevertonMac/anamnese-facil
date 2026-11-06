"""Provedor Anthropic (Messages API via httpx)."""
from __future__ import annotations

import os

import httpx

from app.modules.chat.llm.base import LLMError, LLMNotConfigured, LLMResult


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str) -> None:
        self.model = model

    async def chat(self, system, messages, max_tokens, temperature=0.7) -> LLMResult:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise LLMNotConfigured("ANTHROPIC_API_KEY não configurada.")
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                    json={
                        "model": self.model,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "system": system,
                        "messages": messages,
                    },
                )
            resp.raise_for_status()
            data = resp.json()
            usage = data.get("usage") or {}
            text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
            return LLMResult(
                text=text,
                prompt_tokens=int(usage.get("input_tokens", 0)),
                completion_tokens=int(usage.get("output_tokens", 0)),
                model=data.get("model", self.model),
                provider=self.name,
            )
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise LLMError(f"Anthropic: {e.__class__.__name__}: {e}") from e
