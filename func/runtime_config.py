import json
import signal
import time
from pathlib import Path
from typing import Any, Dict, Set

from func.state import set_manual_on_off, set_schedule_mode, schedule_mode

try:
    from var import const
except Exception:  # pragma: no cover
    const = None

try:
    from var import tipicos
except Exception:  # pragma: no cover
    tipicos = None

try:
    from var import regist
except Exception:  # pragma: no cover
    regist = None

# Normalizar la ruta del runtime_config para que no dependa del cwd del proceso
# (cuando el servicio se levanta via systemd o un shell script sin `cd`).
_RC_PATH = Path(getattr(const, "runtime_config_file", "var/runtime_config.json"))
if not _RC_PATH.is_absolute():
    # Proyecto raíz = carpeta padre de este archivo (func/..)
    _RC_PATH = Path(__file__).resolve().parent.parent / _RC_PATH
RUNTIME_CONFIG_FILE = _RC_PATH
POLL_SECONDS = float(getattr(const, "runtime_config_poll_seconds", 1.0))

_ALLOWED_TOP = {
    "tipico",
    "on_off_global",
    "schedule_mode",
    "mode",
    "setpoints",
    "settings",
    "manual_overrides",
}
_ALLOWED_SETTINGS = {
    # Sensores y offsets
    "temp_supply_offset",
    "temp_return_offset",
    "humidity_offset",
    "raw_ai_microamps",

    # Modo de control
    "control_mode",

    # PIDs principales
    "pid_temp_kp",
    "pid_temp_ki",
    "pid_temp_kd",
    "pid_hum_kp",
    "pid_hum_ki",
    "pid_hum_kd",
    "pid_heat_kp",
    "pid_heat_ki",
    "pid_heat_kd",

    # Heater / reheat
    "heater_max_pct",
    "heater_slew_down_pct_per_s",
    "heater_alarm_pct",
    "reheat_hum_gain_deg_per_pct",

    # Válvula y VFD
    "valve_pid_kp",
    "valve_pid_ki",
    "valve_pid_kd",
    "valve_deadband_c",
    "valve_min_output_hold_time_seconds",
    "valve_tracking_timeout_seconds",
    "feedback_tolerance_volts",
    "vfd_tracking_timeout_seconds",
    "vfd_speed_command_pct",
    "vfd_speed_command_volts",
    "valve_vfd_track_tol",
    "valve_vfd_track_timeout_seconds",

    # Compuerta OA
    "oa_damper_voltage_on",
    "oa_damper_voltage_off",

    # UV
    "uv_status_timeout_seconds",

    # Tiempos / monitoreo
    "fan_feedback_timeout_seconds",
    "status_timeout_seconds",
    "startup_delay_seconds",
    "stage2_min_delay_seconds",

    # MQTT / ingest
    "mqtt_enabled",
    "ingest_enabled",
    "ingest_interval_seconds",
    "mqtt_status_interval_seconds",

    # Setpoints por defecto y monitor
    "temperature_setpoint_default",
    "humidity_setpoint_default",
    "monitor_enabled",
    "supply_high_temp_alarm_enabled",
    "supply_high_temp_alarm_threshold_c",
    "supply_high_temp_alarm_delay_seconds",

    # Reset automatico
    "reset_auto_enabled",
    "reset_auto_poll_seconds",
    "reset_auto_pulse_seconds",
    "reset_auto_clear_grace_seconds",
    "reset_auto_total_shutdown_alarms",
}

# Grupos para filtrado condicional
_HUMIDITY_SETTINGS: Set[str] = {
    "pid_hum_kp",
    "pid_hum_ki",
    "pid_hum_kd",
    "humidity_offset",
    "humidity_setpoint_default",
    "reheat_hum_gain_deg_per_pct",
}

_HEATER_SETTINGS: Set[str] = {
    "heater_max_pct",
    "heater_slew_down_pct_per_s",
    "heater_alarm_pct",
    "reheat_hum_gain_deg_per_pct",
    "pid_heat_kp",
    "pid_heat_ki",
    "pid_heat_kd",
}

_UV_SETTINGS: Set[str] = {"uv_status_timeout_seconds"}

_VFD_SETTINGS: Set[str] = {
    "vfd_speed_command_pct",
    "vfd_speed_command_volts",
    "vfd_tracking_timeout_seconds",
    "valve_vfd_track_tol",
    "valve_vfd_track_timeout_seconds",
}

_OA_DAMPER_SETTINGS: Set[str] = {"oa_damper_voltage_on", "oa_damper_voltage_off"}
_SUPPLY_TEMP_ALARM_SETTINGS: Set[str] = {
    "supply_high_temp_alarm_enabled",
    "supply_high_temp_alarm_threshold_c",
    "supply_high_temp_alarm_delay_seconds",
}
_RESET_AUTO_BOOL_SETTINGS: Set[str] = {"reset_auto_enabled"}
_RESET_AUTO_SEQUENCE_SETTINGS: Set[str] = {"reset_auto_total_shutdown_alarms"}

# Overrides manuales
_OVERRIDE_ALWAYS: Set[str] = {"fan", "heater"}
_OVERRIDE_ANALOG_0_10: Set[str] = {"control_valvula", "control_compuerta_aire_exterior"}
_OVERRIDE_PERCENT_0_100: Set[str] = {"heater", "control_frec_vfd"}


def _as_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _normalize_string_list(value: Any) -> list:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _as_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        t = v.strip().lower()
        if t in ("1", "true", "on", "yes", "si"):
            return True
        if t in ("0", "false", "off", "no"):
            return False
    if isinstance(v, (int, float)):
        return bool(v)
    return default


def allowed_keys_for_tipico(tipico_id: int) -> Dict[str, Set[str]]:
    """Deriva listas blancas por típico para sensores, actuadores, setpoints y settings.

    - Sensores/actuadores: union de required_* de tipicos.py y nombres de registros en var/regist.py
      (inputs/discrete → sensores, holding/coil → actuadores).
    - setpoints: siempre temperatura; humedad solo si aplica al típico.
    - settings: parte de _ALLOWED_SETTINGS, removiendo grupos según features y uso de humedad.
    """

    allowed_sensors: Set[str] = set()
    allowed_actuators: Set[str] = set()
    features: Dict[str, Any] = {}

    if tipicos:
        try:
            cfg = tipicos.get_tipico_config(tipico_id)
            allowed_sensors |= set(cfg.get("required_sensors", set()))
            allowed_actuators |= set(cfg.get("required_actuators", set()))
            features = dict(cfg.get("features", {}))
        except Exception:
            pass

    if regist:
        try:
            for reg in regist.get_registers_for_tipico(tipico_id):
                name = reg.get("name")
                if not name:
                    continue
                rtype = str(reg.get("type", ""))
                if rtype in ("input", "discrete"):
                    allowed_sensors.add(name)
                elif rtype in ("holding", "coil"):
                    allowed_actuators.add(name)
        except Exception:
            pass

    tipico_usa_humedad = "humedad" in allowed_sensors

    allowed_setpoints = {"temperature"}
    if tipico_usa_humedad:
        allowed_setpoints.add("humidity")

    allowed_settings: Set[str] = set(_ALLOWED_SETTINGS)

    if not features.get("usa_heater", False):
        allowed_settings -= _HEATER_SETTINGS
    if not features.get("usa_uv", False):
        allowed_settings -= _UV_SETTINGS
    if not features.get("usa_vfd", False):
        allowed_settings -= _VFD_SETTINGS
    if not features.get("usa_oa_damper", False):
        allowed_settings -= _OA_DAMPER_SETTINGS
    if not tipico_usa_humedad:
        allowed_settings -= _HUMIDITY_SETTINGS
    if "temperatura_suministro" not in allowed_sensors:
        allowed_settings -= _SUPPLY_TEMP_ALARM_SETTINGS

    allowed_override_outputs = set(allowed_actuators) | set(_OVERRIDE_ALWAYS)

    return {
        "allowed_sensors": allowed_sensors,
        "allowed_actuators": allowed_actuators,
        "allowed_override_outputs": allowed_override_outputs,
        "allowed_setpoints": allowed_setpoints,
        "allowed_settings": allowed_settings,
        "tipico_usa_humedad": tipico_usa_humedad,
    }


def _clamp_override_value(key: str, value: Any) -> Any:
    if key in _OVERRIDE_ANALOG_0_10:
        try:
            return max(0.0, min(10.0, float(value)))
        except Exception:
            return 0.0
    if key in _OVERRIDE_PERCENT_0_100:
        try:
            return max(0.0, min(100.0, float(value)))
        except Exception:
            return 0.0
    return _as_bool(value, False)


def _filter_manual_overrides(manual: Dict[str, Any], tipico_id: int) -> Dict[str, Any]:
    allowed = allowed_keys_for_tipico(tipico_id)["allowed_override_outputs"]
    src = manual or {}
    out: Dict[str, Any] = {}
    for key in allowed:
        if key in src:
            out[key] = _clamp_override_value(key, src.get(key))
        forced_key = f"{key}_forced"
        if forced_key in src:
            out[forced_key] = _as_bool(src.get(forced_key), False)
    return out


def _filter_setpoints(setpoints: Dict[str, Any], tipico_id: int) -> Dict[str, Any]:
    allowed = allowed_keys_for_tipico(tipico_id)["allowed_setpoints"]
    return {k: v for k, v in (setpoints or {}).items() if k in allowed}


def _feature_filtered_settings(settings: Dict[str, Any], tipico_id: int) -> Dict[str, Any]:
    """Filtra settings según el típico activo y la lista blanca permitida."""
    allowed = allowed_keys_for_tipico(tipico_id)["allowed_settings"]

    filtered = {k: v for k, v in (settings or {}).items() if k in allowed}
    if "vfd_speed_command_volts" in filtered and "vfd_speed_command_pct" not in filtered:
        filtered["vfd_speed_command_pct"] = max(
            0.0,
            min(100.0, _as_float(filtered.get("vfd_speed_command_volts"), 10.0) * 10.0),
        )
    filtered.pop("vfd_speed_command_volts", None)

    if "control_mode" in filtered:
        filtered["control_mode"] = str(filtered.get("control_mode", "TEMP_HUM")).upper()
    if "reset_auto_total_shutdown_alarms" in filtered:
        filtered["reset_auto_total_shutdown_alarms"] = _normalize_string_list(
            filtered.get("reset_auto_total_shutdown_alarms")
        )

    return filtered


def _snapshot_editable(shared_state) -> Dict[str, Any]:
    tipico_id = int(shared_state.get("tipico", getattr(tipicos, "DEFAULT_TIPICO", 1)))
    settings = _feature_filtered_settings(shared_state.get("settings", {}), tipico_id)
    setpoints = _filter_setpoints(shared_state.get("setpoints", {}), tipico_id)
    manual = _filter_manual_overrides(shared_state.get("manual_overrides", {}), tipico_id)
    return {
        "tipico": tipico_id,
        "on_off_global": bool(shared_state.get("on_off_global", True)),
        "schedule_mode": schedule_mode(shared_state),
        "mode": str(shared_state.get("mode", "AUTO")),
        "setpoints": setpoints,
        "settings": settings,
        "manual_overrides": manual,
        "ts": time.time(),
    }


def _atomic_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def apply_runtime_config_once(shared_state) -> bool:
    """Carga una vez el archivo runtime_config.json en shared_state.

    - Si el archivo existe, aplica sus valores permitidos y devuelve True.
    - Si no existe, genera uno con el snapshot actual y devuelve False.
    """
    try:
        if RUNTIME_CONFIG_FILE.exists():
            with RUNTIME_CONFIG_FILE.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            _apply(shared_state, payload, on_off_override=False)
            return True

        _atomic_write(RUNTIME_CONFIG_FILE, _snapshot_editable(shared_state))
    except Exception as exc:  # pragma: no cover - defensivo
        print(f"[runtime_config] No se pudo aplicar config inicial: {exc}")

    return False


def _apply(shared_state, payload: Dict[str, Any], *, on_off_override: bool = False) -> None:
    if not isinstance(payload, dict):
        return

    # Asegura que "tipico" se procese antes que otros campos para que el filtrado
    # de settings use el nuevo típico.
    keys = list(payload.keys())
    if "tipico" in payload:
        keys = ["tipico"] + [k for k in keys if k != "tipico"]

    for key in keys:
        if key not in _ALLOWED_TOP:
            continue
        if key == "tipico":
            try:
                shared_state["tipico"] = int(payload["tipico"])
            except Exception:
                pass
        elif key == "on_off_global":
            set_manual_on_off(shared_state, payload["on_off_global"], override=True)
        elif key == "schedule_mode":
            set_schedule_mode(shared_state, payload["schedule_mode"])
        elif key == "mode":
            shared_state["mode"] = str(payload["mode"]).upper()
        elif key == "setpoints":
            sp = shared_state.get("setpoints")
            tipico_id = int(shared_state.get("tipico", getattr(tipicos, "DEFAULT_TIPICO", 1)))
            allowed_sp = allowed_keys_for_tipico(tipico_id)["allowed_setpoints"]
            if sp is not None and isinstance(payload.get("setpoints"), dict):
                if "temperature" in payload["setpoints"] and "temperature" in allowed_sp:
                    sp["temperature"] = _as_float(payload["setpoints"]["temperature"], sp.get("temperature", 20.0))
                if "humidity" in payload["setpoints"] and "humidity" in allowed_sp:
                    sp["humidity"] = _as_float(payload["setpoints"]["humidity"], sp.get("humidity", 60.0))
        elif key == "settings":
            st = shared_state.get("settings")
            tipico_id = int(shared_state.get("tipico", getattr(tipicos, "DEFAULT_TIPICO", 1)))
            allowed_settings = allowed_keys_for_tipico(tipico_id)["allowed_settings"]
            src = _feature_filtered_settings(payload.get("settings") or {}, tipico_id)
            if st is not None and isinstance(src, dict):
                for sk, sv in src.items():
                    if sk not in allowed_settings:
                        continue
                    if sk in {"mqtt_enabled", "ingest_enabled", "raw_ai_microamps", "monitor_enabled"}:
                        st[sk] = _as_bool(sv, bool(st.get(sk, True)))
                    elif sk in _RESET_AUTO_BOOL_SETTINGS:
                        st[sk] = _as_bool(sv, bool(st.get(sk, True)))
                    elif sk in _RESET_AUTO_SEQUENCE_SETTINGS:
                        normalized = _normalize_string_list(sv)
                        if normalized:
                            st[sk] = normalized
                    elif sk == "control_mode":
                        st[sk] = str(sv).upper()
                    else:
                        st[sk] = _as_float(sv, _as_float(st.get(sk, 0.0), 0.0))
        elif key == "manual_overrides":
            mo = shared_state.get("manual_overrides")
            tipico_id = int(shared_state.get("tipico", getattr(tipicos, "DEFAULT_TIPICO", 1)))
            src = _filter_manual_overrides(payload.get("manual_overrides") or {}, tipico_id)
            if mo is not None and isinstance(src, dict):
                for mk, mv in src.items():
                    mo[mk] = mv


def runtime_config_loop(shared_state, stop_event):
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except Exception:
        pass

    last_mtime = None
    # bootstrap file
    try:
        if not RUNTIME_CONFIG_FILE.exists():
            _atomic_write(RUNTIME_CONFIG_FILE, _snapshot_editable(shared_state))
            last_mtime = RUNTIME_CONFIG_FILE.stat().st_mtime
    except Exception as exc:
        print(f"[runtime_config] No se pudo inicializar archivo: {exc}")

    while not stop_event.is_set():
        try:
            # 1) leer cambios externos
            if RUNTIME_CONFIG_FILE.exists():
                mt = RUNTIME_CONFIG_FILE.stat().st_mtime
                if last_mtime is None or mt > last_mtime:
                    with RUNTIME_CONFIG_FILE.open("r", encoding="utf-8") as f:
                        payload = json.load(f)
                    _apply(shared_state, payload, on_off_override=last_mtime is not None)
                    last_mtime = mt

            # 2) reflejar estado actual editable en archivo en tiempo real
            _atomic_write(RUNTIME_CONFIG_FILE, _snapshot_editable(shared_state))
            last_mtime = RUNTIME_CONFIG_FILE.stat().st_mtime

        except Exception as exc:
            print(f"[runtime_config] Error: {exc}")

        time.sleep(max(0.25, POLL_SECONDS))
