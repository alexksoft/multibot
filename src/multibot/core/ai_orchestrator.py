from __future__ import annotations
import logging

from ..config.sections import AIPolicy, AssistantProfile
from .capabilities.registry import CapabilityRegistry
from .knowledge import KnowledgeBase
from .providers.kiro_gateway import KiroGatewayProvider, FallbackProvider, ProviderResult

logger = logging.getLogger(__name__)


class AIOrchestrator:
    def __init__(
        self,
        policy: AIPolicy,
        profile: AssistantProfile,
        knowledge: KnowledgeBase,
        capabilities: CapabilityRegistry,
        provider: KiroGatewayProvider | FallbackProvider,
    ):
        self._policy = policy
        self._profile = profile
        self._knowledge = knowledge
        self._caps = capabilities
        self._provider = provider

    async def respond(self, user_text: str, history: list[dict], collected: dict) -> str:
        # 1. Check forbidden advice
        for forbidden in self._policy.forbidden_advice:
            if forbidden.lower() in user_text.lower():
                return (
                    f"Вибачте, я не можу надавати {forbidden}. "
                    "Остаточне рішення — за фахівцем. "
                    "Можу допомогти підготувати питання до нього."
                )

        # 2. FAQ priority
        faq = self._knowledge.match_faq(user_text)
        if faq:
            return faq.answer

        # 3. LLM if enabled
        if not self._policy.enabled:
            return self._policy.fallback_message or "Уточніть питання."

        # Build tools list from allowed_tools
        tools = None
        if self._policy.allowed_tools:
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": f"Execute capability: {name}",
                        "parameters": {"type": "object", "properties": {}, "required": []},
                    },
                }
                for name in self._policy.allowed_tools
                if self._caps.is_allowed(name)
            ]

        result: ProviderResult = await self._provider.complete(
            system=self._policy.system_prompt,
            messages=[*history, {"role": "user", "content": user_text}],
            model=self._policy.model,
            max_tokens=self._policy.max_tokens,
            tools=tools or None,
        )

        # Handle tool calls — only allowed tools
        if result.tool_calls:
            responses = []
            for tc in result.tool_calls:
                name = tc.get("name", "")
                if not self._caps.is_allowed(name):
                    logger.warning(f"[ai] LLM requested disallowed tool: {name}")
                    continue
                cap_result = await self._caps.run(name, {**collected, **tc.get("arguments", {})})
                responses.append(cap_result.text)
            if responses:
                return "\n\n".join(responses)

        return result.content or "Не вдалося отримати відповідь. Спробуйте ще раз."
