import multiprocessing
from collections import deque
import os
import signal
import sys
import time
import json
from pathlib import Path

from func import control, ingesta, modbus, mqtt, runtime_config
from var import const
from var import tipicos

SETPOINTS_FILE = Path(getattr(const, "setpoints_file", "logs/setpoints.json"))


def _load_persisted_setpoints(default_temp: float, default_hum: float) -> tuple:
    """
    Intenta cargar setpoints persistidos desde disco. Si falla o no existe, devuelve los defaults.
    """
    try:
        if SETPOINTS_FILE.exists():
            with SETPOINTS_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f) or {}
            temp = float(data.get("temperature", default_temp))
            hum = float(data.get("humidity", default_hum))
            return temp, hum
    except Exception:
        pass
    return default_temp, default_hum


def create_shared_state(manager: multiprocessing.Manager):
    default_temp = getattr(const, "temperature_setpoint_default", 20.0)
    default_hum = getattr(const, "humidity_setpoint_default", 55.0)
    temp_sp, hum_sp = _load_persisted_setpoints(default_temp, default_hum)
    tipico_default = int(getattr(const, "tipico_default", tipicos.DEFAULT_TIPICO))

    return manager.dict(
        {
            "on_off_global": True,
            "mode": "AUTO",
            "tipico": tipico_default,
            "last_modbus_ok": False,
            "forced_inputs": manager.dict({}),  # overrides de sensores para simulación/testing
            "setpoints": manager.dict(
                {
                    "temperature": temp_sp,
                    "humidity": hum_sp,
                }
            ),
            "settings": manager.dict(
                {
                    "fan_feedback_timeout_seconds": float(getattr(const, "fan_feedback_timeout_seconds", 45.0)),
                    "feedback_tolerance_volts": float(getattr(const, "feedback_tolerance_volts", 1.0)),
                    "valve_tracking_timeout_seconds": float(getattr(const, "valve_tracking_timeout_seconds", 60.0)),
                    "vfd_tracking_timeout_seconds": float(getattr(const, "vfd_tracking_timeout_seconds", 60.0)),
                    "vfd_speed_command_pct": float(
                        getattr(
                            const,
                            "vfd_speed_command_pct",
                            float(getattr(const, "vfd_speed_command_volts", 10.0)) * 10.0,
                        )
                    ),
                    "oa_damper_voltage_on": float(getattr(const, "oa_damper_voltage_on", 10.0)),
                    "oa_damper_voltage_off": float(getattr(const, "oa_damper_voltage_off", 0.0)),
                    "mqtt_enabled": bool(getattr(const, "mqtt_enabled", True)),
                    "ingest_enabled": bool(getattr(const, "ingest_enabled", True)),
                    "ingest_interval_seconds": float(getattr(const, "ingest_interval_seconds", 10.0)),
                    "mqtt_status_interval_seconds": float(getattr(const, "mqtt_status_interval", 30.0)),
                    "valve_pid_kp": float(getattr(const, "valve_pid_kp", 1.2)),
                    "valve_pid_ki": float(getattr(const, "valve_pid_ki", 0.0)),
                    "valve_pid_kd": float(getattr(const, "valve_pid_kd", 0.0)),
                    "valve_deadband_c": float(getattr(const, "valve_deadband_c", 0.2)),
                    "valve_min_output_hold_time_seconds": float(getattr(const, "valve_min_output_hold_time_seconds", 30.0)),
                    "control_mode": str(getattr(const, "control_mode", "TEMP_HUM")),
                    "temp_supply_offset": float(getattr(const, "temp_supply_offset", 0.0)),
                    "temp_return_offset": float(getattr(const, "temp_return_offset", 0.0)),
                    "humidity_offset": float(getattr(const, "humidity_offset", 0.0)),
                    "raw_ai_microamps": bool(getattr(const, "raw_ai_microamps", True)),
                    "pid_temp_kp": float(getattr(const, "pid_temp", {}).get("kp", 1.0)),
                    "pid_temp_ki": float(getattr(const, "pid_temp", {}).get("ki", 0.05)),
                    "pid_temp_kd": float(getattr(const, "pid_temp", {}).get("kd", 0.0)),
                    "pid_hum_kp": float(getattr(const, "pid_hum", {}).get("kp", 1.0)),
                    "pid_hum_ki": float(getattr(const, "pid_hum", {}).get("ki", 0.05)),
                    "pid_hum_kd": float(getattr(const, "pid_hum", {}).get("kd", 0.0)),
                    "pid_heat_kp": float(getattr(const, "pid_heat", {}).get("kp", 15.0)),
                    "pid_heat_ki": float(getattr(const, "pid_heat", {}).get("ki", 0.5)),
                    "pid_heat_kd": float(getattr(const, "pid_heat", {}).get("kd", 0.0)),
                    "heater_max_pct": float(getattr(const, "heater_max_pct", 60.0)),
                    "heater_slew_down_pct_per_s": float(getattr(const, "heater_slew_down_pct_per_s", 2.0)),
                    "heater_alarm_pct": float(getattr(const, "heater_alarm_pct", 30.0)),
                    "reheat_hum_gain_deg_per_pct": float(getattr(const, "reheat_hum_gain_deg_per_pct", 0.05)),
                    "cool_stage1_on_pct": float(getattr(const, "cool_stage1_on_pct", 8.0)),
                    "cool_stage1_off_pct": float(getattr(const, "cool_stage1_off_pct", 4.0)),
                    "cool_stage2_on_pct": float(getattr(const, "cool_stage2_on_pct", 35.0)),
                    "cool_stage2_off_pct": float(getattr(const, "cool_stage2_off_pct", 22.0)),
                    "min_on_comp_seconds": float(getattr(const, "min_on_comp_seconds", 60.0)),
                    "min_off_comp_seconds": float(getattr(const, "min_off_comp_seconds", 60.0)),
                    "startup_delay_seconds": float(getattr(const, "startup_delay_seconds", 30.0)),
                    "stage2_min_delay_seconds": float(getattr(const, "stage2_min_delay_seconds", 60.0)),
                    "first_comp_start_delay_seconds": float(getattr(const, "first_comp_start_delay_seconds", 30.0)),
                    "status_timeout_seconds": float(getattr(const, "status_timeout_seconds", 300.0)),
                    "uv_status_timeout_seconds": float(getattr(const, "uv_status_timeout_seconds", 20.0)),
                    "valve_vfd_track_tol": float(getattr(const, "valve_vfd_track_tol", 0.8)),
                    "valve_vfd_track_timeout_seconds": float(getattr(const, "valve_vfd_track_timeout_seconds", 20.0)),
                    "comp_status_alarm_enabled": bool(getattr(const, "comp_status_alarm_enabled", True)),
                    "temperature_setpoint_default": float(getattr(const, "temperature_setpoint_default", 20.0)),
                    "humidity_setpoint_default": float(getattr(const, "humidity_setpoint_default", 60.0)),
                    "monitor_enabled": bool(getattr(const, "monitor_enabled", True)),
                    "process_restart_max_attempts": int(getattr(const, "process_restart_max_attempts", 3)),
                    "process_restart_backoff_seconds": float(getattr(const, "process_restart_backoff_seconds", 2.0)),
                    "process_restart_window_seconds": float(getattr(const, "process_restart_window_seconds", 300.0)),
                }
            ),
            "manual_overrides": manager.dict(
                {
                    "fan": False,
                    "heater": 0.0,
                    "comando_contactor": False,
                    "comando_vfd": False,
                    "control_frec_vfd": 0.0,
                    "control_valvula": 0.0,
                    "control_compuerta_aire_exterior": 0.0,
                    "comando_luz_ultravioleta": False,
                    "fan_forced": False,
                    "heater_forced": False,
                    "comando_contactor_forced": False,
                    "comando_vfd_forced": False,
                    "control_frec_vfd_forced": False,
                    "control_valvula_forced": False,
                    "control_compuerta_aire_exterior_forced": False,
                    "comando_luz_ultravioleta_forced": False,
                }
            ),
            "resets": manager.dict(
                {
                    "fan": 0,
                    "fan_vel": 0,
                    "valvula": 0,
                    "humo": 0,
                    "heater": 0,
                    "all": 0,
                }
            ),
            "sensors": manager.dict(
                {
                    # Legacy
                    "supply_temp": 0.0,
                    "return_temp": 0.0,
                    "humidity": 0.0,
                    "fan_status": 0,
                    "filter_status": 0,
                    "heater_status": 0,
                    # Canónico típicos
                    "temperatura_suministro": 0.0,
                    "temperatura_retorno": 0.0,
                    "retroalimentacion_valvula": 0.0,
                    "frecuencia_vfd": 0.0,
                    "presion_filtro_hepa": 0.0,
                    "presion_ducto_suministro": 0.0,
                    "co2_retorno": 0.0,
                    "posicion_compuerta_oa": 0.0,
                    "estatus_ventilador": 0,
                    "estatus_prefiltro": 0,
                    "estatus_filtro": 0,
                    "detector_humo": 0,
                    "alarma_vfd": 0,
                    "alarma_termica": 0,
                    "posicion_automatico": 1,
                    "posicion_manual": 0,
                    "estatus_luz_ultravioleta": 0,
                    "estatus_calentador": 0,
                }
            ),
            "actuators": manager.dict(
                {
                    # Legacy
                    "fan": False,
                    "heater": 0.0,
                    # Canónico típicos
                    "comando_contactor": False,
                    "comando_vfd": False,
                    "control_frec_vfd": 0.0,
                    "control_valvula": 0.0,
                    "control_compuerta_aire_exterior": 0.0,
                    "comando_luz_ultravioleta": False,
                }
            ),
            "alarms": manager.dict(
                {
                    # Legacy
                    "fan": False,
                    "heater": False,
                    # Típicos
                    "interlock_humo": False,
                    "interlock_termica": False,
                    "interlock_manual": False,
                    "interlock_vfd": False,
                    "alerta_ventilador": False,
                    "alerta_tracking_valvula": False,
                    "alerta_tracking_vfd": False,
                    "alerta_tracking_vfd_valvula": False,
                    "alerta_uv": False,
                }
            ),
            "safe_mode": False,
            "safe_mode_reason": "",
            "process_failures": manager.dict({}),
            "activation_ts": manager.dict(
                {
                    "fan": 0.0,
                    "heater": 0.0,
                    "ventilador": 0.0,
                    "tracking_valvula": 0.0,
                    "tracking_vfd": 0.0,
                }
            ),
        }
    )


def start_process(target, args, name: str):
    proc = multiprocessing.Process(target=target, args=args, name=name)
    proc.daemon = True
    proc.start()
    print(f"[main] Proceso {name} iniciado (pid={proc.pid})")
    return proc


def _restart_limits(shared_state) -> tuple[int, float, float]:
    settings = shared_state.get("settings") or {}
    max_attempts = max(1, int(settings.get("process_restart_max_attempts", 3)))
    backoff_seconds = max(0.1, float(settings.get("process_restart_backoff_seconds", 2.0)))
    window_seconds = max(backoff_seconds, float(settings.get("process_restart_window_seconds", 300.0)))
    return max_attempts, backoff_seconds, window_seconds


def _activate_safe_mode(shared_state, reason: str) -> None:
    shared_state["safe_mode"] = True
    shared_state["safe_mode_reason"] = reason
    shared_state["on_off_global"] = False
    try:
        alarms = shared_state.get("alarms")
        if alarms is not None:
            alarms["safe_mode"] = True
    except Exception:
        pass
    print(f"[main] safe_mode activado: {reason}")


def _process_specs(shared_state, stop_event):
    return [
        {
            "name": "runtime_config",
            "target": runtime_config.runtime_config_loop,
            "args": (shared_state, stop_event),
            "restart_policy": "always",
            "critical": False,
            "failure_count": 0,
        },
        {
            "name": "modbus",
            "target": modbus.modbus_loop,
            "args": (shared_state, stop_event),
            "restart_policy": "always",
            "critical": True,
            "failure_count": 0,
        },
        {
            "name": "control",
            "target": control.control_loop,
            "args": (shared_state, stop_event),
            "restart_policy": "always",
            "critical": True,
            "failure_count": 0,
        },
        {
            "name": "ingesta",
            "target": ingesta.ingesta_loop,
            "args": (shared_state, stop_event),
            "restart_policy": "always",
            "critical": False,
            "failure_count": 0,
        },
        {
            "name": "mqtt",
            "target": mqtt.mqtt_loop,
            "args": (shared_state, stop_event),
            "restart_policy": "always",
            "critical": False,
            "failure_count": 0,
        },
    ]


def _start_spec(spec: dict):
    spec["proc"] = start_process(spec["target"], spec["args"], spec["name"])
    spec["pending_restart"] = False
    spec["restart_blocked"] = False


def _record_process_failure(shared_state, spec: dict, now_ts: float) -> tuple[int, int]:
    max_attempts, backoff_seconds, window_seconds = _restart_limits(shared_state)
    failures = spec.setdefault("failures", deque())
    while failures and now_ts - failures[0] > window_seconds:
        failures.popleft()
    failures.append(now_ts)
    spec["failure_count"] = len(failures)
    spec["next_restart_ts"] = now_ts + backoff_seconds * (2 ** max(0, spec["failure_count"] - 1))
    try:
        shared_state["process_failures"][spec["name"]] = spec["failure_count"]
    except Exception:
        pass
    return spec["failure_count"], max_attempts


def _supervise_processes(process_specs: list, shared_state, stop_event) -> None:
    now_ts = time.time()
    for spec in process_specs:
        proc = spec.get("proc")
        if proc is None or proc.is_alive():
            continue
        proc.join(timeout=0)
        if stop_event.is_set() or spec.get("restart_policy") != "always" or spec.get("restart_blocked"):
            continue
        if not spec.get("pending_restart"):
            failures, max_attempts = _record_process_failure(shared_state, spec, now_ts)
            print(
                f"[main] Proceso {spec['name']} detenido exitcode={proc.exitcode}; "
                f"fallos={failures}/{max_attempts}"
            )
            if failures > max_attempts:
                spec["restart_blocked"] = True
                if spec.get("critical"):
                    _activate_safe_mode(shared_state, f"process_failed:{spec['name']}")
                else:
                    print(f"[main] Límite de restart superado para {spec['name']}; no se reiniciará")
                continue
            print(f"[main] Restart de {spec['name']} programado en {spec['next_restart_ts'] - now_ts:.1f}s")
            spec["pending_restart"] = True
        if spec.get("pending_restart") and now_ts >= spec.get("next_restart_ts", now_ts):
            print(f"[main] Reiniciando proceso {spec['name']} con backoff exponencial")
            _start_spec(spec)


def main():
    manager = multiprocessing.Manager()
    shared_state = create_shared_state(manager)
    stop_event = multiprocessing.Event()
    stop_called = False
    process_specs = []

    # Precarga runtime_config.json antes de lanzar procesos para respetar flags como mqtt/ingest_enabled
    try:
        applied = runtime_config.apply_runtime_config_once(shared_state)
        if applied:
            print("[main] runtime_config.json aplicado antes de iniciar procesos.")
    except Exception as exc:
        print(f"[main] No se pudo precargar runtime_config.json: {exc}")

    def _stop(signum=None, frame=None):
        nonlocal stop_called, process_specs
        if stop_called:
            print(f"[main] Segunda señal ({signum}), forzando cierre...")
            for spec in process_specs:
                proc = spec.get("proc")
                try:
                    if proc and proc.is_alive():
                        proc.kill()
                except Exception:
                    pass
            os._exit(1)
        stop_called = True
        print(f"[main] Señal de parada recibida ({signum}), deteniendo procesos...")
        stop_event.set()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    process_specs = _process_specs(shared_state, stop_event)

    try:
        from func import monitor

        process_specs.append(
            {
                "name": "monitor",
                "target": monitor.monitor_loop,
                "args": (shared_state, stop_event),
                "restart_policy": "always",
                "critical": False,
                "failure_count": 0,
            }
        )
    except Exception as exc:
        print(f"[main] Monitor HTTP no iniciado: {exc}")

    for spec in process_specs:
        spec["failures"] = deque()
        _start_spec(spec)

    print("[main] Manejadora en ejecución. Para pruebas locales puedes editar func/modbus.py y setear FORCED_INPUTS.")
    try:
        from func.modbus import read_registers_snapshot
        read_registers_snapshot()
    except Exception as exc:
        print(f"[main] No se pudo leer snapshot Modbus inicial: {exc}")

    try:
        while not stop_event.is_set():
            _supervise_processes(process_specs, shared_state, stop_event)
            time.sleep(1)
    except KeyboardInterrupt:
        _stop(signal.SIGINT, None)
    finally:
        for spec in process_specs:
            proc = spec.get("proc")
            if proc is None:
                continue
            proc.join(timeout=5)
            if proc.is_alive():
                print(f"[main] Proceso {proc.name} aún activo, se intentará terminar.")
                proc.terminate()
                proc.join(timeout=2)
            if proc.is_alive():
                print(f"[main] Proceso {proc.name} no respondió a terminate(), se matará.")
                try:
                    proc.kill()
                except Exception:
                    pass

        manager.shutdown()
        print("[main] Finalizado.")
        sys.exit(0)


if __name__ == "__main__":
    main()
