from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..config.sections import ConversationFlows, Flow, Step
from .rules import safe_eval
from .storage import DialogState, Storage

if TYPE_CHECKING:
    from .capabilities.registry import CapabilityRegistry
    from .ai_orchestrator import AIOrchestrator

logger = logging.getLogger(__name__)

SESSION_TIMEOUT_SECONDS = 3600


@dataclass
class BotResponse:
    text: str
    # Each inner list is one row of buttons: [(label, callback_data), ...]
    keyboard: list[list[tuple[str, str]]] = field(default_factory=list)
    # Optional file to send as document
    document: bytes | None = None
    document_name: str = "result.pdf"


def _parse_dimension(text: str) -> tuple[float, float] | None:
    m = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s*[xXхХ*]\s*(\d+(?:[.,]\d+)?)\s*$", text.strip())
    if m:
        return float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
    return None


def _validate_answer(step: Step, text: str) -> tuple[bool, str]:
    if step.question_type == "number":
        try:
            val = float(text.replace(",", "."))
        except ValueError:
            return False, "Введіть число."
        if step.min is not None and val < step.min:
            return False, f"Значення має бути не менше {step.min}."
        if step.max is not None and val > step.max:
            return False, f"Значення має бути не більше {step.max}."
        return True, ""
    elif step.question_type == "choice":
        opts = [o.lower() for o in (step.options or [])]
        if text.strip().lower() not in opts:
            return False, f"Оберіть один з варіантів: {', '.join(step.options or [])}."
        return True, ""
    elif step.question_type == "dimension":
        if _parse_dimension(text) is None:
            return False, "Введіть розміри у форматі ШxД, наприклад: 4x5"
        return True, ""
    return True, ""


def _eval_transition(when: str, collected: dict) -> bool:
    try:
        variables = {}
        for k, v in collected.items():
            try:
                variables[k] = float(v)
            except (TypeError, ValueError):
                pass
        return bool(safe_eval(when, variables))
    except Exception:
        return False


def _menu_keyboard(flows: dict) -> list[list[tuple[str, str]]]:
    """One button per flow, one per row."""
    return [[(flow.title, f"flow:{flow.id}")] for flow in flows.values()]


def _choice_keyboard(options: list[str], prefix: str = "choice") -> list[list[tuple[str, str]]]:
    """Two options per row."""
    rows = []
    for i in range(0, len(options), 2):
        row = [(opt, f"{prefix}:{opt}") for opt in options[i:i+2]]
        rows.append(row)
    return rows


def _suggestion_keyboard(suggestions: list[str]) -> list[list[tuple[str, str]]]:
    """Preset quick-pick buttons (2 per row) + 'Enter manually' button."""
    rows = []
    for i in range(0, len(suggestions), 2):
        row = [(s, f"suggestion:{s}") for s in suggestions[i:i+2]]
        rows.append(row)
    rows.append([("✏️ Ввести своє значення", "suggestion:__manual__")])
    return rows


class FlowEngine:
    def __init__(
        self,
        flows_config: ConversationFlows,
        storage: Storage,
        capabilities: "CapabilityRegistry",
        ai: "AIOrchestrator",
        bot_name: str,
        log_fn=None,
    ):
        self._flows = {f.id: f for f in flows_config.flows}
        self._cancel_commands = [c.lower() for c in flows_config.cancel_commands]
        self._menu_title = flows_config.menu_title
        self._storage = storage
        self._caps = capabilities
        self._ai = ai
        self._bot_name = bot_name
        self._log = log_fn

    def _get_step(self, flow: Flow, step_id: str) -> Step | None:
        for s in flow.steps:
            if s.id == step_id:
                return s
        return None

    def _build_menu(self) -> str:
        lines = [self._menu_title]
        for i, flow in enumerate(self._flows.values(), 1):
            lines.append(f"{i}. {flow.title}")
        return "\n".join(lines)

    def _menu_response(self) -> BotResponse:
        return BotResponse(
            text=self._menu_title,
            keyboard=_menu_keyboard(self._flows),
        )

    async def handle(self, user_id: int, text: str) -> BotResponse:
        text_stripped = text.strip()
        text_lower = text_stripped.lower()

        if text_lower in self._cancel_commands:
            await self._storage.clear_state(self._bot_name, user_id)
            return self._menu_response()

        state = await self._storage.get_state(self._bot_name, user_id)

        if state:
            from datetime import datetime, timezone
            age = (datetime.now(timezone.utc) - state.updated_at).total_seconds()
            if age > SESSION_TIMEOUT_SECONDS:
                await self._storage.clear_state(self._bot_name, user_id)
                state = None

        if not state or not state.flow_id:
            flow_list = list(self._flows.values())

            # Button callback: "flow:estimate"
            if text_lower.startswith("flow:"):
                flow_id = text_stripped[5:]
                flow = self._flows.get(flow_id)
                if flow:
                    return await self._start_flow(user_id, flow)

            # Button callback: "choice:Плитка"
            if text_lower.startswith("choice:"):
                answer = text_stripped[7:]
                for flow in flow_list:
                    first_step = self._get_step(flow, flow.start)
                    if first_step and first_step.question_type == "choice" and first_step.options:
                        if answer.lower() in [o.lower() for o in first_step.options]:
                            return await self._start_flow_with_answer(user_id, flow, answer)

            if text_stripped.isdigit():
                idx = int(text_stripped) - 1
                if 0 <= idx < len(flow_list):
                    return await self._start_flow(user_id, flow_list[idx])

            for flow in flow_list:
                if text_lower in flow.title.lower() or flow.id == text_lower:
                    return await self._start_flow(user_id, flow)

            for flow in flow_list:
                first_step = self._get_step(flow, flow.start)
                if first_step and first_step.question_type == "choice" and first_step.options:
                    if text_lower in [o.lower() for o in first_step.options]:
                        return await self._start_flow_with_answer(user_id, flow, text_stripped)

            ai_text = await self._ai.respond(text_stripped, [], {})
            return BotResponse(
                text=ai_text + f"\n\nℹ️ Скористайтесь меню:",
                keyboard=_menu_keyboard(self._flows),
            )

        flow = self._flows.get(state.flow_id)
        if not flow:
            await self._storage.clear_state(self._bot_name, user_id)
            return self._menu_response()

        step = self._get_step(flow, state.step_id)
        if not step:
            await self._storage.clear_state(self._bot_name, user_id)
            return self._menu_response()

        # Unwrap choice callback during active flow
        if text_lower.startswith("choice:"):
            text_stripped = text_stripped[7:]

        # Unwrap suggestion callback during active flow
        if text_lower.startswith("suggestion:"):
            value = text_stripped[11:]
            if value == "__manual__":
                # User wants to type manually — re-ask the question without buttons
                step_text = step.text or ""
                return BotResponse(step_text + "\n\n✏️ Введіть значення вручну:")
            text_stripped = value

        return await self._execute_step(user_id, flow, step, state, text_stripped)

    async def _start_flow(self, user_id: int, flow: Flow) -> BotResponse:
        state = DialogState(self._bot_name, user_id, flow.id, flow.start)
        await self._storage.save_state(state)
        step = self._get_step(flow, flow.start)
        if not step:
            return BotResponse("Помилка конфігурації сценарію.")
        return await self._execute_step(user_id, flow, step, state, "")

    async def _start_flow_with_answer(self, user_id: int, flow: Flow, answer: str) -> BotResponse:
        state = DialogState(self._bot_name, user_id, flow.id, flow.start)
        await self._storage.save_state(state)
        step = self._get_step(flow, flow.start)
        if not step:
            return BotResponse("Помилка конфігурації сценарію.")
        return await self._execute_step(user_id, flow, step, state, answer)

    async def _execute_step(self, user_id: int, flow: Flow, step: Step,
                             state: DialogState, user_input: str) -> BotResponse:
        if step.kind == "message":
            response_text = step.text or ""
            next_step_id = step.next
            if next_step_id:
                next_step = self._get_step(flow, next_step_id)
                if next_step:
                    state.step_id = next_step_id
                    await self._storage.save_state(state)
                    next_resp = await self._execute_step(user_id, flow, next_step, state, "")
                    combined = (response_text + "\n" + next_resp.text).strip() if next_resp.text else response_text
                    return BotResponse(combined, next_resp.keyboard, next_resp.document, next_resp.document_name)
            else:
                await self._storage.clear_state(self._bot_name, user_id)
            return BotResponse(response_text)

        elif step.kind == "question":
            if user_input:
                valid, err = _validate_answer(step, user_input)
                if not valid:
                    resp = BotResponse(err + f"\n{step.text}")
                    if step.question_type == "choice" and step.options:
                        resp.keyboard = _choice_keyboard(step.options)
                    return resp
                if step.save_as:
                    state.collected[step.save_as] = user_input
                next_id = self._resolve_next(step, state.collected)
                if next_id:
                    next_step = self._get_step(flow, next_id)
                    if next_step:
                        state.step_id = next_id
                        await self._storage.save_state(state)
                        return await self._execute_step(user_id, flow, next_step, state, "")
                await self._storage.clear_state(self._bot_name, user_id)
                return self._menu_response()
            else:
                text = step.text or ""
                keyboard = []
                if step.question_type == "choice" and step.options:
                    keyboard = _choice_keyboard(step.options)
                elif step.suggestions:
                    keyboard = _suggestion_keyboard(step.suggestions)
                return BotResponse(text, keyboard)

        elif step.kind == "capability":
            cap_name = step.capability or ""
            result = await self._caps.run(cap_name, state.collected)
            if cap_name == "calculate_materials" and result.success:
                state.collected["_calc_results"] = result.data
            next_id = self._resolve_next(step, state.collected)
            if next_id:
                next_step = self._get_step(flow, next_id)
                if next_step:
                    state.step_id = next_id
                    await self._storage.save_state(state)
                    next_resp = await self._execute_step(user_id, flow, next_step, state, "")
                    combined = (result.text + "\n\n" + next_resp.text).strip() if next_resp.text else result.text
                    return BotResponse(combined, next_resp.keyboard, next_resp.document, next_resp.document_name)
            await self._storage.clear_state(self._bot_name, user_id)
            # prepare_request returns document
            if result.document:
                return BotResponse(result.text, keyboard=_menu_keyboard(self._flows),
                                   document=result.document, document_name=result.document_name)
            return BotResponse(result.text, keyboard=_menu_keyboard(self._flows))

        elif step.kind == "handoff":
            await self._storage.clear_state(self._bot_name, user_id)
            return BotResponse(step.text or "Передаю запит.", keyboard=_menu_keyboard(self._flows))

        return self._menu_response()

    def _resolve_next(self, step: Step, collected: dict) -> str | None:
        for t in step.transitions:
            if _eval_transition(t.when, collected):
                return t.goto
        return step.next
