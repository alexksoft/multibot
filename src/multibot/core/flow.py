from __future__ import annotations
import logging
import re
from typing import TYPE_CHECKING

from ..config.sections import ConversationFlows, Flow, Step
from .rules import safe_eval
from .storage import DialogState, Storage

if TYPE_CHECKING:
    from .capabilities.registry import CapabilityRegistry
    from .ai_orchestrator import AIOrchestrator

logger = logging.getLogger(__name__)

SESSION_TIMEOUT_SECONDS = 3600  # 1 hour


def _parse_dimension(text: str) -> tuple[float, float] | None:
    """Parse '4x5' or '4.5x3.2' into (width, length)."""
    m = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s*[xXхХ*]\s*(\d+(?:[.,]\d+)?)\s*$", text.strip())
    if m:
        return float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
    return None


def _validate_answer(step: Step, text: str) -> tuple[bool, str]:
    """Validate user answer for a question step. Returns (valid, error_msg)."""
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
        self._log = log_fn  # dialog_log.log_message partial

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

    async def handle(self, user_id: int, text: str) -> str:
        text_stripped = text.strip()
        text_lower = text_stripped.lower()

        # Cancel command
        if text_lower in self._cancel_commands:
            await self._storage.clear_state(self._bot_name, user_id)
            return "Скасовано. " + self._build_menu()

        state = await self._storage.get_state(self._bot_name, user_id)

        # Check session timeout
        if state:
            from datetime import datetime, timezone
            import time
            age = (datetime.now(timezone.utc) - state.updated_at).total_seconds()
            if age > SESSION_TIMEOUT_SECONDS:
                await self._storage.clear_state(self._bot_name, user_id)
                state = None

        # No active flow — show menu or start flow by number/name
        if not state or not state.flow_id:
            flow_list = list(self._flows.values())
            # Try to match by number
            if text_stripped.isdigit():
                idx = int(text_stripped) - 1
                if 0 <= idx < len(flow_list):
                    return await self._start_flow(user_id, flow_list[idx])
            # Try to match by title or any keyword from title
            for flow in flow_list:
                if text_lower in flow.title.lower() or flow.id == text_lower:
                    return await self._start_flow(user_id, flow)
            # Check if user input matches a choice option in the first step of any flow
            # (e.g. user types "плитка" which is an option in the estimate flow)
            for flow in flow_list:
                first_step = self._get_step(flow, flow.start)
                if first_step and first_step.question_type == "choice" and first_step.options:
                    opts_lower = [o.lower() for o in first_step.options]
                    if text_lower in opts_lower:
                        # Start the flow and pre-answer the first question
                        return await self._start_flow_with_answer(user_id, flow, text_stripped)
            # AI free-form response — append menu hint
            response = await self._ai.respond(text_stripped, [], {})
            menu = self._build_menu()
            return response + f"\n\n\u2139\ufe0f Щоб отримати точний розрахунок, скористайтесь меню:\n{menu}"

        # Active flow
        flow = self._flows.get(state.flow_id)
        if not flow:
            await self._storage.clear_state(self._bot_name, user_id)
            return self._build_menu()

        step = self._get_step(flow, state.step_id)
        if not step:
            await self._storage.clear_state(self._bot_name, user_id)
            return self._build_menu()

        return await self._execute_step(user_id, flow, step, state, text_stripped)

    async def _start_flow(self, user_id: int, flow: Flow) -> str:
        state = DialogState(self._bot_name, user_id, flow.id, flow.start)
        await self._storage.save_state(state)
        step = self._get_step(flow, flow.start)
        if not step:
            return "Помилка конфігурації сценарію."
        return await self._execute_step(user_id, flow, step, state, "")

    async def _start_flow_with_answer(self, user_id: int, flow: Flow, answer: str) -> str:
        """Start a flow and immediately provide the answer to the first question."""
        state = DialogState(self._bot_name, user_id, flow.id, flow.start)
        await self._storage.save_state(state)
        step = self._get_step(flow, flow.start)
        if not step:
            return "Помилка конфігурації сценарію."
        return await self._execute_step(user_id, flow, step, state, answer)

    async def _execute_step(self, user_id: int, flow: Flow, step: Step,
                             state: DialogState, user_input: str) -> str:
        if step.kind == "message":
            response = step.text or ""
            next_step_id = step.next
            if next_step_id:
                next_step = self._get_step(flow, next_step_id)
                if next_step:
                    state.step_id = next_step_id
                    await self._storage.save_state(state)
                    next_response = await self._execute_step(user_id, flow, next_step, state, "")
                    return response + "\n" + next_response if next_response else response
            else:
                await self._storage.clear_state(self._bot_name, user_id)
            return response

        elif step.kind == "question":
            # If we have user_input, validate it
            if user_input:
                valid, err = _validate_answer(step, user_input)
                if not valid:
                    return err + f"\n{step.text}"
                # Save answer
                if step.save_as:
                    state.collected[step.save_as] = user_input
                # Determine next step
                next_id = self._resolve_next(step, state.collected)
                if next_id:
                    next_step = self._get_step(flow, next_id)
                    if next_step:
                        state.step_id = next_id
                        await self._storage.save_state(state)
                        return await self._execute_step(user_id, flow, next_step, state, "")
                await self._storage.clear_state(self._bot_name, user_id)
                return self._build_menu()
            else:
                # Ask the question
                text = step.text or ""
                if step.question_type == "choice" and step.options:
                    text += "\n" + "\n".join(f"• {o}" for o in step.options)
                return text

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
                    next_response = await self._execute_step(user_id, flow, next_step, state, "")
                    return result.text + ("\n\n" + next_response if next_response else "")
            await self._storage.clear_state(self._bot_name, user_id)
            return result.text

        elif step.kind == "handoff":
            await self._storage.clear_state(self._bot_name, user_id)
            return step.text or "Передаю запит. " + self._build_menu()

        return self._build_menu()

    def _resolve_next(self, step: Step, collected: dict) -> str | None:
        for t in step.transitions:
            if _eval_transition(t.when, collected):
                return t.goto
        return step.next
