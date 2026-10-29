from __future__ import annotations
import asyncio
import json
import logging
import numpy as np
from pathlib import Path

from ..config.sections import AIPolicy, AssistantProfile
from .capabilities.registry import CapabilityRegistry
from .knowledge import KnowledgeBase
from .providers.kiro_gateway import KiroGatewayProvider, FallbackProvider, ProviderResult

logger = logging.getLogger(__name__)


def _append_to_index(question: str, answer: str, vector_faq) -> None:
    """Save Q&A to a temp file, append vector to index, delete temp file."""
    import time
    temp_file = None
    try:
        if vector_faq is None:
            logger.warning("[ai][step3] vector_faq is None — cannot save Q&A")
            return

        # Step 3: write to unique temp file (timestamp suffix avoids race conditions)
        qa_dir = vector_faq._qa_dir
        ts = int(time.time() * 1000)
        temp_file = qa_dir / f"ai_learned_{ts}.json"
        entry = {"id": ts, "category": "ai_learned", "lang": "uk",
                 "question": question, "answer": answer}
        temp_file.write_text(json.dumps([entry], ensure_ascii=False), encoding="utf-8")
        logger.info("[ai][step3] Q&A saved to %s", temp_file.name)

        # Step 4: encode and append single vector
        logger.info("[ai][step4] appending new vector to existing index...")
        index_path = vector_faq._db_dir / "faq_index.npz"
        model = vector_faq._get_model()

        new_vec = model.encode([question]).astype(np.float32)
        norm = np.linalg.norm(new_vec)
        if norm > 0:
            new_vec = new_vec / norm

        data = np.load(index_path, allow_pickle=True)
        embeddings = np.vstack([data["embeddings"], new_vec])
        answers = list(data["answers"]) + [answer]
        questions = list(data["questions"]) + [question] if "questions" in data else [""] * (len(data["answers"]) - 1) + ["", question]
        block_ids = list(data["block_ids"]) + [-1] if "block_ids" in data else None
        group_keys = data["group_keys"] if "group_keys" in data else np.array([], dtype=np.int32)
        group_langs = data["group_langs"] if "group_langs" in data else np.array([], dtype=object)

        save_kwargs = dict(
            embeddings=embeddings,
            answers=np.array(answers, dtype=object),
            questions=np.array(questions, dtype=object),
            group_keys=group_keys,
            group_langs=group_langs,
        )
        if block_ids is not None:
            save_kwargs["block_ids"] = np.array(block_ids, dtype=np.int32)
        np.savez_compressed(index_path, **save_kwargs)

        # Hot-reload in-memory index
        vector_faq._embeddings = embeddings
        vector_faq._answers = answers
        vector_faq._questions = questions
        if block_ids is not None and vector_faq._block_ids is not None:
            vector_faq._block_ids = np.array(block_ids, dtype=np.int32)

        logger.info("[ai][step4] vector appended. Total vectors: %d", len(answers))

        # Step 5: delete temp file
        temp_file.unlink()
        logger.info("[ai][step5] temp file deleted: %s", temp_file.name)
        temp_file = None

    except Exception as e:
        logger.warning("[ai][step3/4] FAILED: %s", e, exc_info=True)
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass


class AIOrchestrator:
    def __init__(
        self,
        policy: AIPolicy,
        profile: AssistantProfile,
        knowledge: KnowledgeBase,
        capabilities: CapabilityRegistry,
        provider: KiroGatewayProvider | FallbackProvider,
        vector_faq=None,
    ):
        self._policy = policy
        self._profile = profile
        self._knowledge = knowledge
        self._caps = capabilities
        self._provider = provider
        self._vector_faq = vector_faq

    async def respond(self, user_text: str, history: list[dict], collected: dict) -> str:
        logger.info("[ai][step1] question received: %r", user_text[:100])

        # 1. Check forbidden advice
        for forbidden in self._policy.forbidden_advice:
            if forbidden.lower() in user_text.lower():
                return (
                    f"Вибачте, я не можу надавати {forbidden}. "
                    "Остаточне рішення — за фахівцем. "
                    "Можу допомогти підготувати питання до нього."
                )

        # 2. FAQ / vector search
        faq = self._knowledge.match_faq(user_text)
        if faq:
            logger.info("[ai][step1] answered from vector/FAQ — skipping AI")
            return faq.answer
        logger.info("[ai][step1] not found in vector DB — proceeding to AI")

        # 3. LLM if enabled
        if not self._policy.enabled:
            logger.info("[ai][step1] AI disabled — returning fallback")
            return self._policy.fallback_message or "Уточніть питання."

        logger.info("[ai][step2] calling AI model: %s", self._policy.model)
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
        logger.info("[ai][step2] AI responded. has_content=%s has_tool_calls=%s error=%r",
                    bool(result.content), bool(result.tool_calls), result.error or None)

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

        ai_answer = result.content or "Не вдалося отримати відповідь. Спробуйте ще раз."
        logger.info("[ai] Q=%r | A=%r", user_text[:80], ai_answer[:120])

        # Save to vector index in background — only if real AI answer, not fallback
        _FALLBACK_PHRASES = ("тимчасово недоступний", "не вдалося отримати", "Вибачте, AI")
        _SKIP_INDEX_PHRASES = ("🎨", "📐 Скільки", "Це результат розрахунку матеріалів")
        if result.content and not any(p in result.content for p in _FALLBACK_PHRASES) and not any(p in user_text for p in _SKIP_INDEX_PHRASES):
            loop = asyncio.get_running_loop()
            loop.run_in_executor(
                None, _append_to_index, user_text, result.content, self._vector_faq
            )
        elif result.content:
            logger.info("[ai] skipping index — answer looks like fallback")
        return ai_answer
