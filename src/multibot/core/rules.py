from __future__ import annotations
import ast
import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

_ALLOWED_NAMES = {"round", "min", "max", "abs"}  # set for membership check
_ALLOWED_NAMES_SET = _ALLOWED_NAMES
_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Constant,
    ast.Name, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd,
    ast.Load,
)


def safe_eval(expression: str, variables: dict[str, float]) -> float:
    """Evaluate a math expression with allow-listed AST nodes only."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Syntax error in expression: {e}") from e

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"Forbidden node type: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in variables and node.id not in _ALLOWED_NAMES_SET:
            raise ValueError(f"Unknown variable: {node.id}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_NAMES:
                raise ValueError(f"Forbidden function: {ast.dump(node.func)}")

    env = {k: float(v) for k, v in variables.items()}
    env.update({"round": round, "min": min, "max": max, "abs": abs})
    return float(eval(compile(tree, "<expr>", "eval"), {"__builtins__": {}}, env))


class RuleEngine:
    """Evaluates calculation_rules using collected values and norms."""

    def compute(
        self,
        rules: list,
        collected: dict[str, Any],
        norms: dict[str, float],
    ) -> dict[str, dict]:
        variables: dict[str, float] = {}

        # Expand dimension variables (e.g. room → room_width, room_length, room_area)
        for key, val in collected.items():
            if isinstance(val, str):
                # Normalize Cyrillic х/Х to Latin x before dimension check
                normalized = val.replace('\u0445', 'x').replace('\u0425', 'x')
                if "x" in normalized.lower():
                    parts = normalized.lower().replace(",", ".").split("x")
                    if len(parts) == 2:
                        try:
                            w, l = float(parts[0].strip()), float(parts[1].strip())
                            variables[f"{key}_width"] = w
                            variables[f"{key}_length"] = l
                            variables[f"{key}_area"] = w * l
                            variables[f"{key}_perimeter"] = 2 * (w + l)
                        except ValueError:
                            pass
                    else:
                        try:
                            variables[key] = float(val)
                        except (TypeError, ValueError):
                            pass
                else:
                    try:
                        variables[key] = float(val)
                    except (TypeError, ValueError):
                        pass

        variables.update({k: float(v) for k, v in norms.items()})

        results: dict[str, dict] = {}
        for rule in rules:
            try:
                value = safe_eval(rule.expression, variables)
                if rule.round_to is not None:
                    value = round(value, rule.round_to)
                    if rule.round_to == 0:
                        value = int(value)
                variables[rule.id] = float(value)
                results[rule.id] = {"label": rule.label, "value": value, "unit": rule.unit or ""}
            except Exception as e:
                logger.warning(f"[rules] Skipping rule '{rule.id}': {e}")

        return results
