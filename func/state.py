"""Helpers de estado operativo compartido."""

from typing import Any, Dict

SCHEDULE_MODE_AUTO = "AUTO"
SCHEDULE_MODE_MANUAL_ON = "MANUAL_ON"
SCHEDULE_MODE_MANUAL_OFF = "MANUAL_OFF"
SCHEDULE_MODES = {SCHEDULE_MODE_AUTO, SCHEDULE_MODE_MANUAL_ON, SCHEDULE_MODE_MANUAL_OFF}


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


def normalize_schedule_mode(value: Any, default: str = SCHEDULE_MODE_AUTO) -> str:
    mode = str(value or default).strip().upper()
    if mode in SCHEDULE_MODES:
        return mode
    if mode in {"MANUAL", "ON", "POWER_ON", "FORCE_ON"}:
        return SCHEDULE_MODE_MANUAL_ON
    if mode in {"OFF", "POWER_OFF", "FORCE_OFF"}:
        return SCHEDULE_MODE_MANUAL_OFF
    return default


def schedule_mode(shared_state) -> str:
    return normalize_schedule_mode(shared_state.get("schedule_mode", SCHEDULE_MODE_AUTO))


def manual_on_off_request(shared_state) -> bool:
    return _as_bool(shared_state.get("on_off_global", True), True)


def calendar_request(shared_state) -> bool:
    calendar = calendar_state(shared_state)
    if not _as_bool(calendar.get("enabled", False), False):
        return True
    return _as_bool(calendar.get("q", True), True)


def calculate_on_off_effective(shared_state) -> bool:
    return manual_on_off_request(shared_state) and calendar_request(shared_state)


def sync_on_off_effective(shared_state) -> bool:
    effective = calculate_on_off_effective(shared_state)
    shared_state["on_off_effective"] = effective
    return effective


def set_schedule_mode(shared_state, mode: Any) -> str:
    normalized = normalize_schedule_mode(mode)
    shared_state["schedule_mode"] = normalized
    if normalized == SCHEDULE_MODE_MANUAL_ON:
        shared_state["on_off_global"] = True
    elif normalized == SCHEDULE_MODE_MANUAL_OFF:
        shared_state["on_off_global"] = False
    sync_on_off_effective(shared_state)
    return normalized


def set_manual_on_off(shared_state, value: Any, *, override: bool = True) -> bool:
    command = _as_bool(value, True)
    shared_state["on_off_global"] = command
    if override:
        shared_state["schedule_mode"] = SCHEDULE_MODE_MANUAL_ON if command else SCHEDULE_MODE_MANUAL_OFF
    sync_on_off_effective(shared_state)
    return command


def set_auto_schedule(shared_state) -> str:
    return set_schedule_mode(shared_state, SCHEDULE_MODE_AUTO)


def effective_on_off_global(shared_state) -> bool:
    """Lee la habilitación efectiva publicada por este módulo."""
    stored = shared_state.get("on_off_effective", None)
    if stored is None:
        return sync_on_off_effective(shared_state)
    return _as_bool(stored, True)


def power_policy_snapshot(shared_state) -> Dict[str, Any]:
    mode = schedule_mode(shared_state)
    effective = sync_on_off_effective(shared_state)
    return {
        "schedule_mode": mode,
        "manual_request": manual_on_off_request(shared_state),
        "calendar_request": calendar_request(shared_state),
        "effective_on_off": effective,
        "on_off_effective": effective,
    }
