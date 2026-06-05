import signal
import time
from typing import Dict, Any

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

from utilities import write_data, json_formatter

try:
    from var import const
except Exception:  # pragma: no cover - defensivo
    const = None

MEASUREMENT = getattr(const, "influx_measurement", "manejadora")
INGEST_INTERVAL = getattr(const, "ingest_interval_seconds", 10)
INGEST_ENABLED_DEFAULT = getattr(const, "ingest_enabled", True)


def _as_int(value: Any) -> int:
    return 1 if bool(value) else 0


def build_payload(shared_state) -> Dict[str, Any]:
    sensors = shared_state.get("sensors") or {}
    actuators = shared_state.get("actuators") or {}
    setpoints = shared_state.get("setpoints") or {}
    alarms = shared_state.get("alarms") or {}
    overrides = shared_state.get("manual_overrides") or {}
    resets = shared_state.get("resets") or {}
    enabled = bool(shared_state.get("on_off_global", True))

    fields = {
        "tipico": int(shared_state.get("tipico", 1)),
        "temp_supply": float(sensors.get("temperatura_suministro", sensors.get("supply_temp", 0.0))),
        "temp_return": float(sensors.get("temperatura_retorno", sensors.get("return_temp", 0.0))),
        "humidity": float(sensors.get("humidity", 0.0)),
        "detector_humo": _as_int(sensors.get("detector_humo", 0)),
        "alarma_vfd_di": _as_int(sensors.get("alarma_vfd", 0)),
        "alarma_termica_di": _as_int(sensors.get("alarma_termica", 0)),
        "fan_status_di": _as_int(sensors.get("estatus_ventilador", sensors.get("fan_status", 0))),
        "fan_status": _as_int(sensors.get("fan_status", 0)),
        "filter_status": _as_int(sensors.get("filter_status", 0)),
        "heater_status": _as_int(sensors.get("heater_status", 0)),
        "sp_temp": float(setpoints.get("temperature", 0.0)),
        "sp_humidity": float(setpoints.get("humidity", 0.0)),
        "cmd_fan": _as_int(actuators.get("fan", 0)),
        "cmd_heater": float(actuators.get("heater", 0.0)),
        "cmd_contactor": _as_int(actuators.get("comando_contactor", 0)),
        "cmd_vfd": _as_int(actuators.get("comando_vfd", 0)),
        "ao_vfd": float(actuators.get("control_frec_vfd", 0.0)),
        "ao_valvula": float(actuators.get("control_valvula", 0.0)),
        "cmd_solenoide_1": _as_int(actuators.get("solenoid1", 0)),
        "cmd_solenoide_2": _as_int(actuators.get("solenoid2", 0)),
        "on_off_global": _as_int(enabled),
        "mode_manual": 1 if str(shared_state.get("mode", "AUTO")).upper() == "MANUAL" else 0,
        "alarm_fan": _as_int(alarms.get("fan", False)),
        # compresores eliminados
        "alarm_heater": _as_int(alarms.get("heater", False)),
        "alarm_interlock_humo": _as_int(alarms.get("interlock_humo", False)),
        "alarm_interlock_termica": _as_int(alarms.get("interlock_termica", False)),
        "alarm_interlock_vfd": _as_int(alarms.get("interlock_vfd", False)),
        "alarm_fan_feedback": _as_int(alarms.get("alerta_ventilador", False)),
        "alarm_tracking_valvula": _as_int(alarms.get("alerta_tracking_valvula", False)),
        "alarm_tracking_vfd": _as_int(alarms.get("alerta_tracking_vfd", False)),
        "force_fan": _as_int(overrides.get("fan_forced", False)),
        # compresores eliminados
        "force_heater": _as_int(overrides.get("heater_forced", False)),
        "reset_fan": _as_int(resets.get("fan", 0)),
        # compresores eliminados
        "reset_heater": _as_int(resets.get("heater", 0)),
        "reset_all": _as_int(resets.get("all", 0)),
    }

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
