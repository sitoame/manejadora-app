"""Helpers de estado operativo compartido."""

from typing import Any, Dict


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "on", "yes", "si", "sí"}:
            return True
        if normalized in {"0", "false", "off", "no"}:
            return False
    return bool(value)


def calendar_state(shared_state) -> Dict[str, Any]:
    state = shared_state.get("calendar")
    return state if state is not None else {}


def set_manual_on_off(shared_state, value: Any, *, override: bool = True) -> bool:
    command = _as_bool(value, True)
    shared_state["on_off_global"] = command
    calendar = shared_state.get("calendar")
    if calendar is not None:
        calendar["manual_override"] = bool(override)
    return command


def effective_on_off_global(shared_state) -> bool:
    """Calcula habilitacion efectiva: override manual > comando AND calendario."""
    manual_command = _as_bool(shared_state.get("on_off_global", True), True)
    calendar = calendar_state(shared_state)
    if _as_bool(calendar.get("manual_override", False), False):
        return manual_command
    if not _as_bool(calendar.get("enabled", False), False):
        return manual_command
    return manual_command and _as_bool(calendar.get("q", True), True)
