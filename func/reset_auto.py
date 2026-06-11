import signal
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Set, Tuple

try:
    from var import const
except Exception:  # pragma: no cover - defensivo
    const = None


DEFAULT_TOTAL_SHUTDOWN_ALARMS = (
    "fan",
    "alerta_ventilador",
    "interlock_humo",
    "interlock_termica",
    "interlock_vfd",
    "interlock_temp_suministro_alta",
)

FIRST_RESET_DELAYS_SECONDS = (
    5.0 * 60.0,
    30.0 * 60.0,
    60.0 * 60.0,
)
REPEAT_RESET_INTERVAL_SECONDS = 2.0 * 60.0 * 60.0

ENABLED_DEFAULT = bool(getattr(const, "reset_auto_enabled", True))
POLL_SECONDS_DEFAULT = float(getattr(const, "reset_auto_poll_seconds", 1.0))
PULSE_SECONDS_DEFAULT = float(getattr(const, "reset_auto_pulse_seconds", 2.0))
CLEAR_GRACE_SECONDS_DEFAULT = float(
    getattr(
        const,
        "reset_auto_clear_grace_seconds",
        max(
            60.0,
            float(getattr(const, "status_timeout_seconds", 300.0)),
            float(getattr(const, "fan_feedback_timeout_seconds", 45.0)),
            float(getattr(const, "supply_high_temp_alarm_delay_seconds", 60.0)),
        ),
    )
)


@dataclass
class AutoResetState:
    first_alarm_ts: float = 0.0
    last_active_ts: float = 0.0
    last_reset_ts: float = 0.0
    resets_done: int = 0
    pulse_until_ts: float = 0.0
    active_alarm_keys: Set[str] = field(default_factory=set)


class ManagerDisconnectedError(RuntimeError):
    """El proceso manager dejó de estar disponible durante el shutdown."""


def _now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str) -> None:
    try:
        print(f"[reset_auto {_now_str()}] {msg}", flush=True)
    except Exception:
        pass


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("1", "true", "on", "yes", "si"):
            return True
        if normalized in ("0", "false", "off", "no"):
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _is_manager_disconnect(exc: Exception) -> bool:
    if isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, EOFError)):
        return True
    if isinstance(exc, OSError):
        return getattr(exc, "errno", None) in (32, 104, 107)
    return False


def _shared_get(shared_state, key: str, default=None):
    try:
        return shared_state.get(key, default)
    except Exception as exc:
        if _is_manager_disconnect(exc):
            raise ManagerDisconnectedError(key) from exc
        raise


def _configured_alarm_keys(settings: Dict[str, Any]) -> Tuple[str, ...]:
    configured = getattr(const, "reset_auto_total_shutdown_alarms", DEFAULT_TOTAL_SHUTDOWN_ALARMS)
    if "reset_auto_total_shutdown_alarms" in settings:
        configured = settings.get("reset_auto_total_shutdown_alarms")

    if isinstance(configured, str):
        return tuple(k.strip() for k in configured.split(",") if k.strip())

    try:
        return tuple(str(k) for k in configured if str(k))
    except Exception:
        return DEFAULT_TOTAL_SHUTDOWN_ALARMS


def _active_total_shutdown_alarms(alarms: Dict[str, Any], alarm_keys: Iterable[str]) -> Set[str]:
    return {key for key in alarm_keys if bool(alarms.get(key, False))}


def _next_due_ts(first_alarm_ts: float, resets_done: int) -> float:
    if resets_done < len(FIRST_RESET_DELAYS_SECONDS):
        return first_alarm_ts + FIRST_RESET_DELAYS_SECONDS[resets_done]

    repeats_done = resets_done - len(FIRST_RESET_DELAYS_SECONDS)
    return first_alarm_ts + FIRST_RESET_DELAYS_SECONDS[-1] + (
        REPEAT_RESET_INTERVAL_SECONDS * float(repeats_done + 1)
    )


def _reset_sequence(state: AutoResetState) -> None:
    state.first_alarm_ts = 0.0
    state.last_active_ts = 0.0
    state.last_reset_ts = 0.0
    state.resets_done = 0
    state.active_alarm_keys.clear()


def _publish_status(shared_state, state: AutoResetState, enabled: bool, now: float) -> None:
    status = _shared_get(shared_state, "reset_auto")
    if status is None:
        return

    next_due = 0.0
    seconds_to_next = 0.0
    if state.first_alarm_ts:
        next_due = _next_due_ts(state.first_alarm_ts, state.resets_done)
        seconds_to_next = max(0.0, next_due - now)

    try:
        status["enabled"] = bool(enabled)
        status["active"] = bool(state.first_alarm_ts)
        status["active_alarm_keys"] = sorted(state.active_alarm_keys)
        status["first_alarm_ts"] = state.first_alarm_ts
        status["last_active_ts"] = state.last_active_ts
        status["last_reset_ts"] = state.last_reset_ts
        status["resets_done"] = int(state.resets_done)
        status["next_reset_ts"] = next_due
        status["seconds_to_next_reset"] = seconds_to_next
        status["pulse_active"] = bool(state.pulse_until_ts and now < state.pulse_until_ts)
        status["ts"] = now
    except Exception:
        pass


def _clear_auto_pulse(shared_state, state: AutoResetState, now: float, force: bool = False) -> None:
    if not state.pulse_until_ts:
        return
    if not force and now < state.pulse_until_ts:
        return

    resets = _shared_get(shared_state, "resets")
    if resets is not None:
        try:
            resets["all"] = 0
        except Exception:
            pass
    state.pulse_until_ts = 0.0


def _clear_alarms_and_timers(shared_state) -> None:
    alarms = _shared_get(shared_state, "alarms")
    activation_ts = _shared_get(shared_state, "activation_ts")

    if alarms is not None:
        try:
            for key in list(alarms.keys()):
                alarms[key] = False
        except Exception:
            pass

    if activation_ts is not None:
        try:
            for key in list(activation_ts.keys()):
                activation_ts[key] = 0.0
        except Exception:
            pass


def _pulse_reset_all(shared_state, state: AutoResetState, now: float, pulse_seconds: float) -> None:
    resets = _shared_get(shared_state, "resets")
    if resets is not None:
        try:
            resets["all"] = 1
        except Exception:
            pass
    state.pulse_until_ts = now + max(0.1, pulse_seconds)


def _run_auto_reset(
    shared_state,
    state: AutoResetState,
    now: float,
    active_keys: Set[str],
    pulse_seconds: float,
) -> None:
    attempt = state.resets_done + 1
    _clear_alarms_and_timers(shared_state)
    _pulse_reset_all(shared_state, state, now, pulse_seconds)
    state.resets_done = attempt
    state.last_reset_ts = now
    state.last_active_ts = now
    state.active_alarm_keys = set(active_keys)
    _log(
        "reset automatico #%s generado por alarmas=%s"
        % (attempt, ",".join(sorted(active_keys)) or "-")
    )


def reset_auto_loop(shared_state, stop_event, poll_seconds: float = None) -> None:
    """
    Genera resets automaticos acumulativos para alarmas que apagan la manejadora:
      - 1er reset: 5 min desde la primera alarma activa.
      - 2do reset: 30 min desde la primera alarma.
      - 3er reset: 1 h desde la primera alarma.
      - Siguientes: cada 2 h despues del tercer reset.

    La secuencia se conserva durante un breve periodo despues de cada reset para
    que una alarma que se regenere no vuelva a empezar desde el primer intento.
    """
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except Exception:
        pass

    state = AutoResetState()
    poll = max(0.25, _safe_float(poll_seconds, POLL_SECONDS_DEFAULT))
    _log("loop iniciado")

    while not stop_event.is_set():
        now = time.time()
        try:
            settings = _shared_get(shared_state, "settings") or {}
            enabled = _safe_bool(settings.get("reset_auto_enabled", ENABLED_DEFAULT), ENABLED_DEFAULT)
            pulse_seconds = max(
                0.1,
                _safe_float(settings.get("reset_auto_pulse_seconds", PULSE_SECONDS_DEFAULT), PULSE_SECONDS_DEFAULT),
            )
            clear_grace = max(
                0.0,
                _safe_float(
                    settings.get("reset_auto_clear_grace_seconds", CLEAR_GRACE_SECONDS_DEFAULT),
                    CLEAR_GRACE_SECONDS_DEFAULT,
                ),
            )

            _clear_auto_pulse(shared_state, state, now)

            if not enabled:
                if state.first_alarm_ts:
                    _log("secuencia cancelada: reset automatico deshabilitado")
                _reset_sequence(state)
                _publish_status(shared_state, state, False, now)
                time.sleep(poll)
                continue

            alarms = _shared_get(shared_state, "alarms") or {}
            active_keys = _active_total_shutdown_alarms(alarms, _configured_alarm_keys(settings))

            if not active_keys:
                state.active_alarm_keys.clear()
                if state.first_alarm_ts:
                    should_clear = state.resets_done == 0 or (now - state.last_active_ts) >= clear_grace
                    if should_clear:
                        _log("secuencia finalizada: alarmas criticas despejadas")
                        _reset_sequence(state)
                _publish_status(shared_state, state, True, now)
                time.sleep(poll)
                continue

            if not state.first_alarm_ts:
                state.first_alarm_ts = now
                state.resets_done = 0
                state.last_reset_ts = 0.0
                _log("secuencia iniciada por alarmas=%s" % ",".join(sorted(active_keys)))

            state.last_active_ts = now
            state.active_alarm_keys = set(active_keys)

            due_ts = _next_due_ts(state.first_alarm_ts, state.resets_done)
            if now >= due_ts:
                _run_auto_reset(shared_state, state, now, active_keys, pulse_seconds)

            _publish_status(shared_state, state, True, now)
        except ManagerDisconnectedError:
            _log("manager desconectado; cerrando loop")
            break
        except Exception as exc:  # pragma: no cover - proteccion runtime
            _log(f"error en ciclo: {exc}")

        time.sleep(poll)

    try:
        _clear_auto_pulse(shared_state, state, time.time(), force=True)
        _publish_status(shared_state, state, ENABLED_DEFAULT, time.time())
    except ManagerDisconnectedError:
        pass
