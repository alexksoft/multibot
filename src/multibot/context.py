from __future__ import annotations
from dataclasses import dataclass

from dataclasses import dataclass

from .config.sections import BotConfig
from .core.capabilities.registry import CapabilityRegistry
from .core.ai_orchestrator import AIOrchestrator
from .core.flow import FlowEngine
from .core.integrations.delivery import ResultDelivery
from .core.knowledge import KnowledgeBase
from .core.storage import Storage


@dataclass
class BotContext:
    config: BotConfig
    knowledge: KnowledgeBase
    capabilities: CapabilityRegistry
    ai: AIOrchestrator
    flow_engine: FlowEngine
    delivery: ResultDelivery
    storage: Storage
