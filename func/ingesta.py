import signal
import time
from typing import Dict, Any, Callable, Iterable, Set

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

from utilities import write_data, json_formatter

try:
    from var import const
except Exception:  # pragma: no cover - defensivo
    const = None

try:
    from var import tipicos
except Exception:  # pragma: no cover - defensivo
    tipicos = None

try:
    from func import runtime_config
except Exception:  # pragma: no cover - defensivo
    runtime_config = None

MEASUREMENT = getattr(const, "influx_measurement", "manejadora")
INGEST_INTERVAL = getattr(const, "ingest_interval_seconds", 10)
INGEST_ENABLED_DEFAULT = getattr(const, "ingest_enabled", True)


def _as_int(value: Any) -> int:
    return 1 if bool(value) else 0


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


FieldGetter = Callable[[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]], Any]


def _sensor_value(*keys: str, default: Any = 0.0, as_int: bool = False) -> FieldGetter:
    def getter(sensors, _actuators, _setpoints, _alarms, _overrides, _resets):
        for key in keys:
            if key in sensors:
                value = sensors.get(key)
                return _as_int(value) if as_int else _as_float(value, _as_float(default))
        return _as_int(default) if as_int else _as_float(default)

    return getter


def _actuator_value(key: str, default: Any = 0.0, as_int: bool = False) -> FieldGetter:
    def getter(_sensors, actuators, _setpoints, _alarms, _overrides, _resets):
        value = actuators.get(key, default)
        return _as_int(value) if as_int else _as_float(value, _as_float(default))

    return getter


def _alarm_value(key: str) -> FieldGetter:
    def getter(_sensors, _actuators, _setpoints, alarms, _overrides, _resets):
        return _as_int(alarms.get(key, False))

    return getter


def _override_forced_value(key: str) -> FieldGetter:
    forced_key = f"{key}_forced"

    def getter(_sensors, _actuators, _setpoints, _alarms, overrides, _resets):
        return _as_int(overrides.get(forced_key, False))

    return getter


def _reset_value(key: str) -> FieldGetter:
    def getter(_sensors, _actuators, _setpoints, _alarms, _overrides, resets):
        return _as_int(resets.get(key, 0))

    return getter


def _fan_force_key(features: Dict[str, Any]) -> str:
    if features.get("usa_vfd", False):
        return "comando_vfd"
    if features.get("usa_contactor", False):
        return "comando_contactor"
    return "fan"


def _any_allowed(allowed: Iterable[str], *names: str) -> bool:
    allowed_set = set(allowed)
    return any(name in allowed_set for name in names)


def _allowed_for_tipico(tipico_id: int) -> Dict[str, Set[str]]:
    if runtime_config:
        try:
            return runtime_config.allowed_keys_for_tipico(tipico_id)
        except Exception:
            pass
    return {
        "allowed_sensors": set(),
        "allowed_actuators": set(),
        "allowed_setpoints": {"temperature"},
    }


SENSOR_FIELD_MAP = {
    "temperatura_suministro": ("temp_supply", _sensor_value("temperatura_suministro", "supply_temp")),
    "temperatura_retorno": ("temp_return", _sensor_value("temperatura_retorno", "return_temp")),
    "humedad": ("humidity", _sensor_value("humidity", "humedad")),
    "retroalimentacion_valvula": ("retroalimentacion_valvula", _sensor_value("retroalimentacion_valvula")),
    "frecuencia_vfd": ("frecuencia_vfd", _sensor_value("frecuencia_vfd")),
    "presion_filtro_hepa": ("presion_filtro_hepa", _sensor_value("presion_filtro_hepa")),
    "presion_ducto_suministro": ("presion_ducto_suministro", _sensor_value("presion_ducto_suministro")),
    "co2_retorno": ("co2_retorno", _sensor_value("co2_retorno")),
    "posicion_compuerta_oa": ("posicion_compuerta_oa", _sensor_value("posicion_compuerta_oa")),
    "estatus_ventilador": ("fan_status_di", _sensor_value("estatus_ventilador", "fan_status", as_int=True)),
    "estatus_prefiltro": ("prefilter_status", _sensor_value("estatus_prefiltro", as_int=True)),
    "estatus_filtro": ("filter_status", _sensor_value("estatus_filtro", "filter_status", as_int=True)),
    "detector_humo": ("detector_humo", _sensor_value("detector_humo", as_int=True)),
    "alarma_vfd": ("alarma_vfd_di", _sensor_value("alarma_vfd", as_int=True)),
    "alarma_termica": ("alarma_termica_di", _sensor_value("alarma_termica", as_int=True)),
    "posicion_automatico": ("posicion_automatico", _sensor_value("posicion_automatico", default=1, as_int=True)),
    "posicion_manual": ("posicion_manual", _sensor_value("posicion_manual", as_int=True)),
    "estatus_luz_ultravioleta": ("uv_status", _sensor_value("estatus_luz_ultravioleta", as_int=True)),
    "estatus_calentador": ("heater_status", _sensor_value("estatus_calentador", "heater_status", as_int=True)),
    "status_ups": ("status_ups", _sensor_value("status_ups", as_int=True)),
    "alarma_ups": ("alarma_ups", _sensor_value("alarma_ups", as_int=True)),
    "battery_disch": ("battery_disch", _sensor_value("battery_disch", as_int=True)),
}

# Entradas discretas que ya tienen una alarma lógica más clara en la ingesta.
RAW_SENSOR_EXCLUDE = {
    # "estatus_ventilador",
    # "detector_humo",
    # "alarma_vfd",
    "alarma_termica",
    "posicion_automatico",
    "posicion_manual",
    "estatus_luz_ultravioleta",
    # "status_ups",
    # "alarma_ups",
    # "battery_disch",
}

ACTUATOR_FIELD_MAP = {
    "comando_contactor": ("cmd_contactor", _actuator_value("comando_contactor", as_int=True)),
    "comando_vfd": ("cmd_vfd", _actuator_value("comando_vfd", as_int=True)),
    "control_frec_vfd": ("ao_vfd", _actuator_value("control_frec_vfd")),
    "control_valvula": ("ao_valvula", _actuator_value("control_valvula")),
    "control_compuerta_aire_exterior": ("ao_compuerta_aire_exterior", _actuator_value("control_compuerta_aire_exterior")),
    "comando_luz_ultravioleta": ("cmd_luz_ultravioleta", _actuator_value("comando_luz_ultravioleta", as_int=True)),
    "comando_ventilador": ("cmd_fan", _actuator_value("fan", as_int=True)),
    "fan": ("cmd_fan", _actuator_value("fan", as_int=True)),
    "heater": ("cmd_heater", _actuator_value("heater")),
    "regulacion_calentador": ("cmd_heater", _actuator_value("heater")),
    "comando_compresor_1": ("cmd_compresor_1", _actuator_value("comp1", as_int=True)),
    "comando_compresor_2": ("cmd_compresor_2", _actuator_value("comp2", as_int=True)),
    "comando_solenoide_1": ("cmd_solenoide_1", _actuator_value("solenoid1", as_int=True)),
    "comando_solenoide_2": ("cmd_solenoide_2", _actuator_value("solenoid2", as_int=True)),
}


def _tipico_features(tipico_id: int) -> Dict[str, Any]:
    if tipicos:
        try:
            return dict(tipicos.get_tipico_config(tipico_id).get("features", {}))
        except Exception:
            pass
    return {}


def build_payload(shared_state) -> Dict[str, Any]:
    sensors = shared_state.get("sensors") or {}
    actuators = shared_state.get("actuators") or {}
    setpoints = shared_state.get("setpoints") or {}
    alarms = shared_state.get("alarms") or {}
    overrides = shared_state.get("manual_overrides") or {}
    resets = shared_state.get("resets") or {}
    enabled = bool(shared_state.get("on_off_global", True))
    tipico_id = int(shared_state.get("tipico", 1))
    allowed = _allowed_for_tipico(tipico_id)
    allowed_sensors = set(allowed.get("allowed_sensors", set()))
    allowed_actuators = set(allowed.get("allowed_actuators", set()))
    allowed_setpoints = set(allowed.get("allowed_setpoints", {"temperature"}))
    features = _tipico_features(tipico_id)

    fields = {
        "tipico": tipico_id,
        "on_off_global": _as_int(enabled),
        "mode_manual": 1 if str(shared_state.get("mode", "AUTO")).upper() == "MANUAL" else 0,
        "reset_all": _as_int(resets.get("all", 0)),
    }

    if "temperature" in allowed_setpoints:
        fields["sp_temp"] = _as_float(setpoints.get("temperature", 0.0))
    if "humidity" in allowed_setpoints:
        fields["sp_humidity"] = _as_float(setpoints.get("humidity", 0.0))

    for reg_name, (field_name, getter) in SENSOR_FIELD_MAP.items():
        if reg_name in allowed_sensors and reg_name not in RAW_SENSOR_EXCLUDE:
            fields[field_name] = getter(sensors, actuators, setpoints, alarms, overrides, resets)

    for reg_name, (field_name, getter) in ACTUATOR_FIELD_MAP.items():
        if reg_name in allowed_actuators and field_name not in fields:
            fields[field_name] = getter(sensors, actuators, setpoints, alarms, overrides, resets)

    if _any_allowed(allowed_sensors, "estatus_ventilador") or _any_allowed(allowed_actuators, "fan", "comando_ventilador", "comando_contactor", "comando_vfd"):
        fields["alarm_fan_feedback"] = _alarm_value("alerta_ventilador")(sensors, actuators, setpoints, alarms, overrides, resets)
        fields["force_fan"] = _override_forced_value(_fan_force_key(features))(sensors, actuators, setpoints, alarms, overrides, resets)
        fields["reset_fan"] = _reset_value("fan")(sensors, actuators, setpoints, alarms, overrides, resets)
        if features.get("usa_vfd", False) or _any_allowed(allowed_actuators, "control_frec_vfd"):
            fields["force_fan_vel"] = _override_forced_value("control_frec_vfd")(sensors, actuators, setpoints, alarms, overrides, resets)
            fields["reset_fan_vel"] = _reset_value("fan_vel")(sensors, actuators, setpoints, alarms, overrides, resets)

    if _any_allowed(allowed_sensors, "detector_humo"):
        fields["alarm_interlock_humo"] = _alarm_value("interlock_humo")(sensors, actuators, setpoints, alarms, overrides, resets)

    if _any_allowed(allowed_sensors, "alarma_termica"):
        fields["alarm_interlock_termica"] = _alarm_value("interlock_termica")(sensors, actuators, setpoints, alarms, overrides, resets)

    if _any_allowed(allowed_sensors, "temperatura_suministro", "supply_temp"):
        fields["alarm_supply_temp_high"] = _alarm_value("interlock_temp_suministro_alta")(
            sensors, actuators, setpoints, alarms, overrides, resets
        )

    if features.get("usa_auto_manual", False) or _any_allowed(allowed_sensors, "posicion_automatico", "posicion_manual"):
        fields["alarm_interlock_manual"] = _alarm_value("interlock_manual")(sensors, actuators, setpoints, alarms, overrides, resets)

    if _any_allowed(allowed_sensors, "alarma_vfd") or _any_allowed(allowed_actuators, "comando_vfd", "control_frec_vfd"):
        fields["alarm_interlock_vfd"] = _alarm_value("interlock_vfd")(sensors, actuators, setpoints, alarms, overrides, resets)
        if tipico_id in (1, 2):
            fields["alarm_tracking_vfd"] = _alarm_value("alerta_tracking_vfd")(sensors, actuators, setpoints, alarms, overrides, resets)

    if tipico_id in (1, 2) and (_any_allowed(allowed_sensors, "retroalimentacion_valvula") or _any_allowed(allowed_actuators, "control_valvula")):
        fields["alarm_tracking_valvula"] = _alarm_value("alerta_tracking_valvula")(sensors, actuators, setpoints, alarms, overrides, resets)

    if tipico_id in (3, 5, 6, 8, 11) and _any_allowed(allowed_actuators, "comando_vfd", "control_frec_vfd", "control_valvula"):
        fields["alarm_tracking_vfd_valvula"] = _alarm_value("alerta_tracking_vfd_valvula")(sensors, actuators, setpoints, alarms, overrides, resets)

    if _any_allowed(allowed_actuators, "control_valvula"):
        fields["force_valvula"] = _override_forced_value("control_valvula")(sensors, actuators, setpoints, alarms, overrides, resets)
        fields["reset_valvula"] = _reset_value("valvula")(sensors, actuators, setpoints, alarms, overrides, resets)

    if _any_allowed(allowed_actuators, "heater", "regulacion_calentador") or _any_allowed(allowed_sensors, "estatus_calentador"):
        fields["force_heater"] = _override_forced_value("heater")(sensors, actuators, setpoints, alarms, overrides, resets)
        fields["reset_heater"] = _reset_value("heater")(sensors, actuators, setpoints, alarms, overrides, resets)

    if _any_allowed(allowed_actuators, "comando_luz_ultravioleta") or _any_allowed(allowed_sensors, "estatus_luz_ultravioleta"):
        fields["alarm_uv"] = _alarm_value("alerta_uv")(sensors, actuators, setpoints, alarms, overrides, resets)

    return json_formatter.formatJson(fields, MEASUREMENT)


def ingesta_loop(shared_state, stop_event, interval_seconds: float = INGEST_INTERVAL) -> None:
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except Exception:
        pass

    client = None
    write_api = None
    ingest_started = False

    while not stop_event.is_set():
        try:
            settings = shared_state.get("settings") or {}
            ingest_enabled = bool(settings.get("ingest_enabled", INGEST_ENABLED_DEFAULT))
            current_interval = float(settings.get("ingest_interval_seconds", interval_seconds))
            current_interval = max(1.0, current_interval)

            if ingest_enabled and not ingest_started:
                client = InfluxDBClient(
                    url=getattr(const, "url_influx", ""),
                    token=getattr(const, "api_token_influx", ""),
                    org=getattr(const, "org_influx", ""),
                    timeout=10_000,
                )
                write_api = client.write_api(write_options=SYNCHRONOUS)
                ingest_started = True
                print(
                    f"[ingesta] Enviando mediciones '{MEASUREMENT}' cada {current_interval}s al bucket '{getattr(const, 'bucket', '')}'"
                )

            if (not ingest_enabled) and ingest_started:
                print("[ingesta] Ingesta desactivada en runtime_config.json")
                try:
                    client.close()
                except Exception:
                    pass
                client = None
                write_api = None
                ingest_started = False
                time.sleep(current_interval)
                continue

            if not ingest_enabled:
                time.sleep(current_interval)
                continue

            if not bool(shared_state.get("last_modbus_ok", True)):
                time.sleep(current_interval)
                continue

            payload = build_payload(shared_state)
            write_data.writeData(MEASUREMENT, payload, write_api)
            time.sleep(current_interval)

        except Exception as exc:  # pragma: no cover - runtime
            print(f"[ingesta] Error al enviar datos a InfluxDB: {exc}")
            time.sleep(2)

    if client:
        client.close()
