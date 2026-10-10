from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-4.7"


@dataclass
class ProviderResult:
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    error: str = ""


class FallbackProvider:
    """No-network fallback: returns FAQ answer or polite message."""

    async def complete(self, system: str, messages: list[dict],
                       model: str | None = None, max_tokens: int = 600,
                       tools: list[dict] | None = None) -> ProviderResult:
        return ProviderResult(
            content="Вибачте, AI-асистент тимчасово недоступний. "
                    "Спробуйте пізніше або скористайтеся меню."
        )


class KiroGatewayProvider:
    def __init__(self, base_url: str, api_key: str, default_model: str = DEFAULT_MODEL):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._default_model = default_model
        self._fallback = FallbackProvider()

    async def complete(
        self,
        system: str,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 600,
        tools: list[dict] | None = None,
    ) -> ProviderResult:
        if not self._base_url or not self._api_key:
            logger.warning("[kiro] Gateway not configured, using fallback")
            return await self._fallback.complete(system, messages, model, max_tokens, tools)

        payload: dict[str, Any] = {
            "model": model or self._default_model,
            "messages": [{"role": "system", "content": system}, *messages],
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                resp = await client.post(
                    f"{self._base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                msg = data["choices"][0]["message"]
                tool_calls = []
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        import json
                        tool_calls.append({
                            "name": tc["function"]["name"],
                            "arguments": json.loads(tc["function"].get("arguments", "{}")),
                        })
                return ProviderResult(content=msg.get("content") or "", tool_calls=tool_calls)
        except Exception as e:
            logger.warning(f"[kiro] Request failed: {e}, using fallback")
            return await self._fallback.complete(system, messages, model, max_tokens, tools)
