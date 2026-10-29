from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-haiku-4-5"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "groq/compound-mini",
    "groq/compound",
]


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


class GroqProvider:
    """Groq API provider with model fallback chain."""

    def __init__(self, api_key: str, default_model: str = GROQ_MODELS[0]):
        self._api_key = api_key
        self._fallback = FallbackProvider()

    async def complete(
        self,
        system: str,
        messages: list[dict],
        model: str | None = None,
        max_tokens: int = 2000,
        tools: list[dict] | None = None,
    ) -> ProviderResult:
        if not self._api_key:
            logger.warning("[groq] API key not configured, using fallback")
            return await self._fallback.complete(system, messages, model, max_tokens, tools)

        for attempt_model in GROQ_MODELS:
            payload: dict[str, Any] = {
                "model": attempt_model,
                "messages": [{"role": "system", "content": system}, *messages],
                "max_tokens": max_tokens,
            }
            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
                    resp = await client.post(
                        GROQ_API_URL,
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    if resp.status_code == 429:
                        logger.warning("[groq] model %s rate limited, trying next", attempt_model)
                        continue
                    if not resp.is_success:
                        logger.warning("[groq] model %s HTTP %s: %s", attempt_model, resp.status_code, resp.text[:200])
                        continue
                    data = resp.json()
                    msg = data["choices"][0]["message"]
                    logger.info("[groq] answered with model %s", attempt_model)
                    return ProviderResult(content=msg.get("content") or "")
            except Exception as e:
                logger.warning("[groq] model %s failed: %s", attempt_model, e)
                continue

        logger.warning("[groq] all models exhausted, using fallback")
        return await self._fallback.complete(system, messages, model, max_tokens, tools)


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
        max_tokens: int = 2000,
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
