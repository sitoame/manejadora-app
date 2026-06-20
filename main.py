import multiprocessing
import os
import signal
import sys
import time
import json
from pathlib import Path

from func import calendario, control, ingesta, modbus, mqtt, reset_auto, runtime_config
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
                    "supply_high_temp_alarm_enabled": bool(getattr(const, "supply_high_temp_alarm_enabled", True)),
                    "supply_high_temp_alarm_threshold_c": float(
                        getattr(const, "supply_high_temp_alarm_threshold_c", 30.0)
                    ),
                    "supply_high_temp_alarm_delay_seconds": float(
                        getattr(const, "supply_high_temp_alarm_delay_seconds", 60.0)
                    ),
                    "reset_auto_enabled": bool(getattr(const, "reset_auto_enabled", True)),
                    "reset_auto_poll_seconds": float(getattr(const, "reset_auto_poll_seconds", 1.0)),
                    "reset_auto_pulse_seconds": float(getattr(const, "reset_auto_pulse_seconds", 2.0)),
                    "reset_auto_clear_grace_seconds": float(
                        getattr(const, "reset_auto_clear_grace_seconds", 300.0)
                    ),
                    "reset_auto_total_shutdown_alarms": list(
                        getattr(reset_auto, "DEFAULT_TOTAL_SHUTDOWN_ALARMS", ())
                    ),
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
                    "interlock_temp_suministro_alta": False,
                }
            ),
            "activation_ts": manager.dict(
                {
                    "fan": 0.0,
                    "heater": 0.0,
                    "ventilador": 0.0,
                    "tracking_valvula": 0.0,
                    "tracking_vfd": 0.0,
                    "temp_suministro_alta": 0.0,
                }
            ),
            "calendar": manager.dict(
                {
                    "enabled": False,
                    "request": False,
                    "q": True,
                    "manual_override": False,
                    "source": "INIT",
                    "detail": "calendario no evaluado",
                    "now_local": "",
                    "timezone": calendario.ZONA_HORARIA,
                    "cycle_seconds": float(calendario.CICLO_SEGUNDOS),
                    "on_delay_seconds": float(calendario.RETARDO_ENCENDIDO_SEG),
                    "off_delay_seconds": float(calendario.RETARDO_APAGADO_SEG),
                    "ts": 0.0,
                }
            ),
            "reset_auto": manager.dict(
                {
                    "enabled": bool(getattr(const, "reset_auto_enabled", True)),
                    "active": False,
                    "active_alarm_keys": [],
                    "first_alarm_ts": 0.0,
                    "last_active_ts": 0.0,
                    "last_reset_ts": 0.0,
                    "resets_done": 0,
                    "next_reset_ts": 0.0,
                    "seconds_to_next_reset": 0.0,
                    "pulse_active": False,
                    "ts": 0.0,
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


def main():
    manager = multiprocessing.Manager()
    shared_state = create_shared_state(manager)
    stop_event = multiprocessing.Event()
    stop_called = False
    processes = []

    # init cfg antes de lanzar procesos para respetar flags y horario operativo
    try:
        applied = runtime_config.apply_runtime_config_once(shared_state)
        if applied:
            print("[main] runtime_config.json aplicado antes de iniciar procesos.")
    except Exception as exc:
        print(f"[main] No se pudo precargar runtime_config.json: {exc}")

    try:
        calendario.apply_calendar_once(shared_state)
        print("[main] Calendario operativo aplicado antes de iniciar procesos.")
    except Exception as exc:
        print(f"[main] No se pudo precargar calendario operativo: {exc}")

    def _stop(signum=None, frame=None):
        nonlocal stop_called, processes
        if stop_called:
            print(f"[main] Segunda señal ({signum}), forzando cierre...")
            for proc in processes:
                try:
                    if proc.is_alive():
                        proc.kill()
                except Exception:
                    pass
            os._exit(1)
        stop_called = True
        print(f"[main] Señal de parada recibida ({signum}), deteniendo procesos...")
        stop_event.set()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    processes = [
        start_process(runtime_config.runtime_config_loop, (shared_state, stop_event), "runtime_config"),
        start_process(calendario.calendario_loop, (shared_state, stop_event), "calendario"),
        start_process(modbus.modbus_loop, (shared_state, stop_event), "modbus"),
        start_process(control.control_loop, (shared_state, stop_event), "control"),
        start_process(reset_auto.reset_auto_loop, (shared_state, stop_event), "reset_auto"),
        start_process(ingesta.ingesta_loop, (shared_state, stop_event), "ingesta"),
        start_process(mqtt.mqtt_loop, (shared_state, stop_event), "mqtt"),
    ]

    try:
        from func import monitor

        processes.append(start_process(monitor.monitor_loop, (shared_state, stop_event), "monitor"))
    except Exception as exc:
        print(f"[main] Monitor HTTP no iniciado: {exc}")

    print("[main] Manejadora en ejecución. Para pruebas locales puedes editar func/modbus.py y setear FORCED_INPUTS.")
    try:
        from func.modbus import read_registers_snapshot
        read_registers_snapshot()
    except Exception as exc:
        print(f"[main] No se pudo leer snapshot Modbus inicial: {exc}")

    try:
        while not stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        _stop(signal.SIGINT, None)
    finally:
        for proc in processes:
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
