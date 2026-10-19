from __future__ import annotations
import ast
from typing import Literal
from pydantic import BaseModel, model_validator, field_validator


# ── Section 1: Assistant Profile ─────────────────────────────────────────────

class AssistantProfile(BaseModel):
    version: int = 1
    series_name: str = "Practical AI Assistants"
    assistant_role: str
    industry: str
    target_user: str
    language: str = "uk"
    tone: str = "friendly"
    disclaimer: str = (
        "Безкоштовний демонстраційний AI-асистент. "
        "Не представляє конкретну компанію чи магазин."
    )
    developer_note: str | None = None


# ── Section 2: Conversation Flows ────────────────────────────────────────────

class Transition(BaseModel):
    when: str
    goto: str


class Step(BaseModel):
    id: str
    kind: Literal["message", "question", "capability", "handoff"]
    text: str | None = None
    question_type: Literal["number", "text", "choice", "dimension"] | None = None
    options: list[str] | None = None
    suggestions: list[str] | None = None  # preset quick-pick buttons for number/dimension (free text still allowed)
    unit: str | None = None
    min: float | None = None
    max: float | None = None
    save_as: str | None = None
    capability: str | None = None
    next: str | None = None
    transitions: list[Transition] = []

    @model_validator(mode="after")
    def _validate_choice(self) -> "Step":
        if self.question_type == "choice" and not self.options:
            raise ValueError(f"Step '{self.id}': choice question requires options")
        return self


class Flow(BaseModel):
    id: str
    title: str
    start: str
    steps: list[Step]

    @model_validator(mode="after")
    def _validate_steps(self) -> "Flow":
        ids = {s.id for s in self.steps}
        if self.start not in ids:
            raise ValueError(f"Flow '{self.id}': start step '{self.start}' not found")
        return self


class ConversationFlows(BaseModel):
    version: int = 1
    menu_title: str = "Оберіть дію:"
    flows: list[Flow]
    cancel_commands: list[str] = ["/cancel", "скасувати"]


# ── Section 3: Capabilities ───────────────────────────────────────────────────

CAPABILITY_NAMES = Literal[
    "calculate_materials", "search_products", "shopping_list",
    "checklist", "questions_for_pro", "compare_options", "prepare_request"
]


class CapabilityRef(BaseModel):
    name: CAPABILITY_NAMES
    params: dict = {}


class Capabilities(BaseModel):
    version: int = 1
    enabled: list[CapabilityRef] = []

    def is_enabled(self, name: str) -> bool:
        return any(c.name == name for c in self.enabled)

    def get_params(self, name: str) -> dict:
        for c in self.enabled:
            if c.name == name:
                return c.params
        return {}


# ── Section 4: Knowledge & Data ───────────────────────────────────────────────

class FAQItem(BaseModel):
    question: str
    answer: str
    keywords: list[str] = []


class CatalogItem(BaseModel):
    category: str
    item: str = ""
    price: float | None = None
    unit: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    collected_at: str | None = None
    package_size: float | None = None
    package_unit: str | None = None
    attributes: dict = {}
    active: bool = True
    notes: str = ""

    @model_validator(mode="after")
    def _price_needs_source(self) -> "CatalogItem":
        if self.price is not None and not self.source_name:
            raise ValueError("price requires source_name (магазин/сайт)")
        return self


class SheetsSource(BaseModel):
    enabled: bool = False
    sheet_id_env: str = "GOOGLE_SHEET_ID"
    worksheet: str | None = None
    cache_ttl_seconds: int = 300


class CalculationRule(BaseModel):
    id: str
    label: str
    expression: str
    unit: str | None = None
    round_to: int | None = None


class KnowledgeData(BaseModel):
    version: int = 1
    faq: list[FAQItem] = []
    catalog: list[CatalogItem] = []
    sheets: SheetsSource = SheetsSource()
    calculation_rules: list[CalculationRule] = []
    norms: dict[str, float] = {}
    work_rules: dict[str, list[str]] = {}  # work_type -> list of rule ids to show


# ── Section 5: AI Policy ──────────────────────────────────────────────────────

class AIPolicy(BaseModel):
    version: int = 1
    enabled: bool = True
    system_prompt: str
    model: str | None = None
    allowed_tools: list[str] = []
    max_tokens: int = 600
    forbidden_advice: list[str] = []
    clarify_when_unsure: bool = True


# ── Section 6: Integrations ───────────────────────────────────────────────────

class RequestField(BaseModel):
    id: str
    label: str
    type: Literal["text", "phone", "choice"]
    required: bool = True
    options: list[str] | None = None


class IntegrationSink(BaseModel):
    type: Literal["telegram_manager", "crm_webhook", "email"]
    enabled: bool = False
    config: dict = {}


class Integrations(BaseModel):
    version: int = 1
    request_form: list[RequestField] = []
    deliver_to_user: bool = True
    sinks: list[IntegrationSink] = []


# ── Booking (feature flag) ────────────────────────────────────────────────────

class BookingConfig(BaseModel):
    version: int = 1
    enabled: bool = False
    provider_term: str = "майстер"
    service_term: str = "послуга"
    demo_masters: int = 5
    contacts_text: str = ""
    intro: str = ""


# ── Root BotConfig ────────────────────────────────────────────────────────────

class BotConfig(BaseModel):
    name: str
    token_env: str
    assistant_profile: AssistantProfile
    conversation_flows: ConversationFlows
    capabilities: Capabilities = Capabilities()
    knowledge: KnowledgeData = KnowledgeData()
    ai_policy: AIPolicy
    integrations: Integrations = Integrations()
    booking: BookingConfig = BookingConfig()
