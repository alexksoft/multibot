from __future__ import annotations
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass
class PreparedResult:
    bot_name: str
    industry: str
    user_id: int
    kind: str
    collected_params: dict
    body_text: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    delivered_to: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "bot_name": self.bot_name,
            "industry": self.industry,
            "user_id": self.user_id,
            "kind": self.kind,
            "collected_params": self.collected_params,
            "body_text": self.body_text,
            "created_at": self.created_at.isoformat(),
            "delivered_to": self.delivered_to,
        }


@runtime_checkable
class ResultSink(Protocol):
    type: str
    enabled: bool

    async def deliver(self, result: PreparedResult) -> bool: ...


class TelegramManagerSink:
    type = "telegram_manager"

    def __init__(self, chat_id: str, bot_token: str):
        self.enabled = bool(chat_id and bot_token)
        self._chat_id = chat_id
        self._bot_token = bot_token

    async def deliver(self, result: PreparedResult) -> bool:
        if not self.enabled:
            return False
        try:
            import httpx
            url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json={
                    "chat_id": self._chat_id,
                    "text": f"[{result.bot_name}] Новий запит:\n{result.body_text}",
                })
                return resp.status_code == 200
        except Exception as e:
            logger.warning(f"[sink:telegram] delivery failed: {e}")
            return False


class ResultDelivery:
    def __init__(self, sinks: list[ResultSink] | None = None):
        self._sinks = [s for s in (sinks or []) if s.enabled]

    async def deliver(self, result: PreparedResult, storage=None) -> str:
        result.delivered_to.append("user")
        if storage:
            await storage.save_result(result.to_dict())
            await storage.incr_counter(result.bot_name, "results")

        for sink in self._sinks:
            ok = await sink.deliver(result)
            if ok:
                result.delivered_to.append(sink.type)
            else:
                logger.warning(f"[delivery] Sink '{sink.type}' failed for result {result.id}")

        return result.body_text
