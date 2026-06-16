import signal
import time
from typing import Dict, Any, Tuple

from var import const
from var import tipicos
from func.pid import PIDController

# PID y umbrales (configurables en const.py)
TEMP_STAGE1_DELTA = getattr(const, "temp_stage1_delta", 0.2)
TEMP_STAGE1_OFF_DELTA = getattr(const, "temp_stage1_off_delta", 0.8)  # histéresis: apaga comp1 cuando baja SP - delta
TEMP_STAGE2_DELTA = getattr(const, "temp_stage2_delta", 0.5)
TEMP_STAGE2_OFF_DELTA = getattr(const, "temp_stage2_off_delta", 0.5)
HUM_STAGE1_DELTA = getattr(const, "hum_stage1_delta", 3.0)
HUM_STAGE2_DELTA = getattr(const, "hum_stage2_delta", 8.0)
STARTUP_DELAY = getattr(const, "startup_delay_seconds", 30.0)
STAGE2_DELAY = getattr(const, "stage2_min_delay_seconds", 180.0)

PID_TEMP = getattr(const, "pid_temp", {"kp": 1.0, "ki": 0.05, "kd": 0.0})
PID_HUM = getattr(const, "pid_hum", {"kp": 0.4, "ki": 0.02, "kd": 0.0})
PID_HEAT = getattr(const, "pid_heat", {"kp": 8.0, "ki": 0.2, "kd": 0.0})

HEATER_MAX = 100.0
HEATER_SLEW_DOWN = max(0.0, float(getattr(const, "heater_slew_down_pct_per_s", 0.0)))
HEATER_ALARM_PCT = max(0.0, min(100.0, float(getattr(const, "heater_alarm_pct", 30.0))))
REHEAT_HUM_GAIN = float(getattr(const, "reheat_hum_gain_deg_per_pct", 0.0))
COOL_STAGE1_ON_PCT = max(0.0, min(100.0, float(getattr(const, "cool_stage1_on_pct", 15.0))))
COOL_STAGE1_OFF_PCT = max(0.0, min(100.0, float(getattr(const, "cool_stage1_off_pct", 8.0))))
COOL_STAGE2_ON_PCT = max(0.0, min(100.0, float(getattr(const, "cool_stage2_on_pct", 55.0))))
COOL_STAGE2_OFF_PCT = max(0.0, min(100.0, float(getattr(const, "cool_stage2_off_pct", 40.0))))
CONTROL_MODE = str(getattr(const, "control_mode", "TEMP_HUM")).upper()
FIRST_COMP_START_DELAY = getattr(const, "first_comp_start_delay_seconds", 60.0)
SUPPLY_HIGH_TEMP_ALARM_ENABLED = bool(getattr(const, "supply_high_temp_alarm_enabled", True))
SUPPLY_HIGH_TEMP_ALARM_THRESHOLD_C = float(getattr(const, "supply_high_temp_alarm_threshold_c", 30.0))
SUPPLY_HIGH_TEMP_ALARM_DELAY_SECONDS = float(getattr(const, "supply_high_temp_alarm_delay_seconds", 60.0))

# Mapa de salidas forzables por típico (confirmado con cliente)
OVERRIDABLE_BY_TIPICO = {
    1: {"comando_contactor", "control_valvula"},
    2: {"comando_vfd", "control_frec_vfd", "control_valvula"},
    3: {
        "comando_vfd",
        "control_frec_vfd",
        "control_valvula",
        "control_compuerta_aire_exterior",
        "heater",
        "comando_luz_ultravioleta",
    },
    5: {"comando_vfd", "control_frec_vfd", "control_valvula", "comando_luz_ultravioleta"},
    6: {"comando_vfd", "control_frec_vfd", "control_valvula", "heater"},
    7: {"comando_contactor", "control_valvula", "control_compuerta_aire_exterior", "heater"},
    8: {"comando_vfd", "control_frec_vfd", "control_valvula", "heater", "comando_luz_ultravioleta"},
    11: {"comando_vfd", "control_frec_vfd", "control_valvula", "comando_luz_ultravioleta"},
    12: {"comando_contactor", "control_valvula", "heater", "comando_luz_ultravioleta"},
    0: {"fan", "heater"},  # rama legacy/generica
}

# Tiempos mínimos para evitar ciclado rápido
MIN_ON_COMP = getattr(const, "min_on_comp_seconds", 60.0)
MIN_OFF_COMP = getattr(const, "min_off_comp_seconds", 60.0)

# Timeout de confirmación de estado (segundos)
STATUS_TIMEOUT = getattr(const, "status_timeout_seconds", 45.0)
COMP_STATUS_ALARM_ENABLED = getattr(const, "comp_status_alarm_enabled", True)

def _log(msg: str) -> None:
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] {msg}", flush=True)
    except Exception:
        pass


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


HEATER_MAX_AUTO = clamp(
    float(getattr(const, "heater_max_pct", HEATER_MAX)),
    0.0,
    HEATER_MAX,
)


def apply_min_cycle(
    key: str,
    desired_on: bool,
    current_on: bool,
    cycle_state: Dict[str, Dict[str, float]],
    now: float,
    min_on: float,
    min_off: float,
    force_off: bool = False,
    ignore_min_off: bool = False,
) -> bool:
    """
    Respeta tiempos mínimos de encendido/apagado para evitar ciclado rápido.
    Si force_off es True, permite apagar de inmediato aunque no haya cumplido min_on.
    Si ignore_min_off es True, permite encender de inmediato aunque no haya cumplido min_off.
    """
    state = cycle_state.setdefault(key, {"on": current_on, "ts": now, "init": True})
    on = state["on"]
    elapsed = now - state["ts"]

    # Primera llamada: permitir cambio inmediato y marcar como inicializado
    if state.pop("init", False):
        if desired_on != on:
            state["on"] = desired_on
            state["ts"] = now
            return desired_on
        return on

    if desired_on != on:
        if on and (not force_off) and elapsed < min_on:
            # Aún no cumplió tiempo mínimo encendido
            return True
        if (not on) and (not ignore_min_off) and elapsed < min_off:
            # Aún no cumplió tiempo mínimo apagado
            return False
        # Cambio permitido
        state["on"] = desired_on
        state["ts"] = now
        return desired_on

    return on


def _stage_from_pid_demand(demand_pct: float, last_stage: int) -> int:
    """
    Convierte una demanda 0-100% en etapas 0/1/2 con histéresis.
    Usa thresholds configurables para evitar serrucho.
    """
    stage = 0

    # Evaluar etapa 2 con histéresis
    if last_stage >= 2:
        stage = 2 if demand_pct >= COOL_STAGE2_OFF_PCT else 1
    else:
        stage = 2 if demand_pct >= COOL_STAGE2_ON_PCT else stage

    # Evaluar etapa 1 con histéresis
    if stage < 1:
        if last_stage >= 1:
            stage = 1 if demand_pct >= COOL_STAGE1_OFF_PCT else 0
        else:
            stage = 1 if demand_pct >= COOL_STAGE1_ON_PCT else 0

    return stage




def _refresh_runtime_params(shared_state) -> float:
    """Actualiza parámetros globales desde shared_state.settings (runtime_config.json)."""
    global STARTUP_DELAY, STAGE2_DELAY, PID_TEMP, PID_HUM, PID_HEAT
    global HEATER_SLEW_DOWN, HEATER_ALARM_PCT, REHEAT_HUM_GAIN
    global COOL_STAGE1_ON_PCT, COOL_STAGE1_OFF_PCT, COOL_STAGE2_ON_PCT, COOL_STAGE2_OFF_PCT
    global CONTROL_MODE, FIRST_COMP_START_DELAY, MIN_ON_COMP, MIN_OFF_COMP
    global STATUS_TIMEOUT, COMP_STATUS_ALARM_ENABLED
    global SUPPLY_HIGH_TEMP_ALARM_ENABLED, SUPPLY_HIGH_TEMP_ALARM_THRESHOLD_C, SUPPLY_HIGH_TEMP_ALARM_DELAY_SECONDS

    settings = shared_state.get("settings") or {}
    CONTROL_MODE = str(settings.get("control_mode", getattr(const, "control_mode", CONTROL_MODE))).upper()
    STARTUP_DELAY = float(settings.get("startup_delay_seconds", STARTUP_DELAY))
    STAGE2_DELAY = float(settings.get("stage2_min_delay_seconds", STAGE2_DELAY))
    FIRST_COMP_START_DELAY = float(settings.get("first_comp_start_delay_seconds", FIRST_COMP_START_DELAY))
    MIN_ON_COMP = float(settings.get("min_on_comp_seconds", MIN_ON_COMP))
    MIN_OFF_COMP = float(settings.get("min_off_comp_seconds", MIN_OFF_COMP))
    STATUS_TIMEOUT = float(settings.get("status_timeout_seconds", STATUS_TIMEOUT))
    COMP_STATUS_ALARM_ENABLED = bool(settings.get("comp_status_alarm_enabled", COMP_STATUS_ALARM_ENABLED))
    SUPPLY_HIGH_TEMP_ALARM_ENABLED = bool(
        settings.get("supply_high_temp_alarm_enabled", SUPPLY_HIGH_TEMP_ALARM_ENABLED)
    )
    SUPPLY_HIGH_TEMP_ALARM_THRESHOLD_C = float(
        settings.get("supply_high_temp_alarm_threshold_c", SUPPLY_HIGH_TEMP_ALARM_THRESHOLD_C)
    )
    SUPPLY_HIGH_TEMP_ALARM_DELAY_SECONDS = float(
        settings.get("supply_high_temp_alarm_delay_seconds", SUPPLY_HIGH_TEMP_ALARM_DELAY_SECONDS)
    )

    PID_TEMP = {
        "kp": float(settings.get("pid_temp_kp", PID_TEMP.get("kp", 1.0))),
        "ki": float(settings.get("pid_temp_ki", PID_TEMP.get("ki", 0.05))),
        "kd": float(settings.get("pid_temp_kd", PID_TEMP.get("kd", 0.0))),
    }
    PID_HUM = {
        "kp": float(settings.get("pid_hum_kp", PID_HUM.get("kp", 1.0))),
        "ki": float(settings.get("pid_hum_ki", PID_HUM.get("ki", 0.05))),
        "kd": float(settings.get("pid_hum_kd", PID_HUM.get("kd", 0.0))),
    }
    PID_HEAT = {
        "kp": float(settings.get("pid_heat_kp", PID_HEAT.get("kp", 15.0))),
        "ki": float(settings.get("pid_heat_ki", PID_HEAT.get("ki", 0.5))),
        "kd": float(settings.get("pid_heat_kd", PID_HEAT.get("kd", 0.0))),
    }

    HEATER_SLEW_DOWN = max(0.0, float(settings.get("heater_slew_down_pct_per_s", HEATER_SLEW_DOWN)))
    HEATER_ALARM_PCT = max(0.0, min(100.0, float(settings.get("heater_alarm_pct", HEATER_ALARM_PCT))))
    REHEAT_HUM_GAIN = float(settings.get("reheat_hum_gain_deg_per_pct", REHEAT_HUM_GAIN))
    COOL_STAGE1_ON_PCT = max(0.0, min(100.0, float(settings.get("cool_stage1_on_pct", COOL_STAGE1_ON_PCT))))
    COOL_STAGE1_OFF_PCT = max(0.0, min(100.0, float(settings.get("cool_stage1_off_pct", COOL_STAGE1_OFF_PCT))))
    COOL_STAGE2_ON_PCT = max(0.0, min(100.0, float(settings.get("cool_stage2_on_pct", COOL_STAGE2_ON_PCT))))
    COOL_STAGE2_OFF_PCT = max(0.0, min(100.0, float(settings.get("cool_stage2_off_pct", COOL_STAGE2_OFF_PCT))))

    heater_max_auto = clamp(float(settings.get("heater_max_pct", getattr(const, "heater_max_pct", HEATER_MAX))), 0.0, HEATER_MAX)
    return heater_max_auto


def _apply_total_fault_shutdown(outputs: Dict[str, Any]) -> None:
    for key in ("fan", "comando_contactor", "comando_vfd", "comando_luz_ultravioleta"):
        if key in outputs:
            outputs[key] = False

    for key in ("heater", "control_frec_vfd", "control_valvula", "control_compuerta_aire_exterior"):
        if key in outputs:
            outputs[key] = 0.0


def _supply_high_temp_fault(
    sensors: Dict[str, Any],
    alarms: Dict[str, Any],
    activation_ts: Dict[str, Any],
    settings: Dict[str, Any],
    now: float,
) -> bool:
    enabled = bool(settings.get("supply_high_temp_alarm_enabled", SUPPLY_HIGH_TEMP_ALARM_ENABLED))
    threshold_c = _safe_float(
        settings.get("supply_high_temp_alarm_threshold_c", SUPPLY_HIGH_TEMP_ALARM_THRESHOLD_C),
        SUPPLY_HIGH_TEMP_ALARM_THRESHOLD_C,
    )
    delay_seconds = max(
        0.0,
        _safe_float(
            settings.get("supply_high_temp_alarm_delay_seconds", SUPPLY_HIGH_TEMP_ALARM_DELAY_SECONDS),
            SUPPLY_HIGH_TEMP_ALARM_DELAY_SECONDS,
        ),
    )
    timer_key = "temp_suministro_alta"
    alarm_key = "interlock_temp_suministro_alta"

    if not enabled or threshold_c <= 0.0 or delay_seconds <= 0.0:
        activation_ts[timer_key] = 0.0
        alarms[alarm_key] = False
        return False

    supply_temp = _safe_float(
        sensors.get("temperatura_suministro", sensors.get("supply_temp", 0.0)),
        0.0,
    )
    if supply_temp <= threshold_c:
        activation_ts[timer_key] = 0.0
        alarms[alarm_key] = False
        return False

    if activation_ts.get(timer_key, 0.0) == 0.0:
        activation_ts[timer_key] = now
        alarms[alarm_key] = False
        return False

    triggered = (now - activation_ts.get(timer_key, 0.0)) >= delay_seconds
    alarms[alarm_key] = triggered
    return triggered


def _manual_outputs(shared_state) -> Tuple[Dict[str, Any], str]:
    overrides = shared_state.get("manual_overrides") or {}
    heater_value = overrides.get("heater", 0.0)
    try:
        heater_value = float(heater_value)
    except Exception:
        heater_value = 0.0

    outputs = {
        "fan": bool(overrides.get("fan", False)),
        "heater": clamp(heater_value, 0.0, HEATER_MAX),
    }
    return outputs, "MANUAL"


def _auto_outputs(shared_state) -> Tuple[Dict[str, Any], str]:
    sensors = shared_state.get("sensors") or {}
    setpoints = shared_state.get("setpoints") or {}

    temp_sp = float(setpoints.get("temperature", 20.0))
    hum_sp = float(setpoints.get("humidity", 60.0))
    return_temp = float(sensors.get("return_temp", 0.0))
    humidity = float(sensors.get("humidity", 0.0))

    # Errores (positivos cuando falta enfriar o secar)
    temp_error_hot = return_temp - temp_sp
    humidity_error = humidity - hum_sp

    # Las salidas PID se actualizan en control_loop (donde está el estado)
    outputs = {
        "fan": True,   # siempre ON mientras el global esté habilitado
        "heater": 0.0,
    }

    info = f"AUTO | errT={temp_error_hot:.2f} errH={humidity_error:.2f}"
    return outputs, info


def _apply_forced(shared_state, outputs: Dict[str, Any]) -> str:
    """Aplica overrides forzados por dispositivo (se usan tanto en AUTO como en MANUAL)."""
    overrides = shared_state.get("manual_overrides") or {}
    forced_info = []

    def _force_bool(key: str):
        if overrides.get(f"{key}_forced", False):
            outputs[key] = bool(overrides.get(key, False))
            forced_info.append(key)

    _force_bool("fan")
    if overrides.get("heater_forced", False):
        try:
            heater_value = float(overrides.get("heater", 0.0))
        except Exception:
            heater_value = 0.0
        outputs["heater"] = clamp(heater_value, 0.0, HEATER_MAX)
        forced_info.append("heater")

    if forced_info:
        return " | FORCED " + ",".join(forced_info)
    return ""


def _apply_forced_outputs_for_tipico(shared_state, outputs: Dict[str, Any], tipico_id: int) -> str:
    """Aplica overrides por típico. No bypassa interlocks, solo reemplaza salidas lógicas.

    - Usa manual_overrides: valor y flag *_forced.
    - Clamps: válvula/dámper AO (0-10 V), VFD speed/heater (0-100 %), digitales -> bool.
    """

    manual = shared_state.get("manual_overrides") or {}
    allowed = OVERRIDABLE_BY_TIPICO.get(int(tipico_id), set())
    forced = []

    def _clamp(key: str, val: Any) -> Any:
        if key == "control_frec_vfd":
            try:
                return max(0.0, min(100.0, float(val)))
            except Exception:
                return 0.0
        if key in {"control_valvula", "control_compuerta_aire_exterior"}:
            try:
                return max(0.0, min(10.0, float(val)))
            except Exception:
                return 0.0
        if key == "heater":
            try:
                return clamp(float(val), 0.0, HEATER_MAX)
            except Exception:
                return 0.0
        return bool(val)

    for key in allowed:
        if manual.get(f"{key}_forced", False):
            outputs[key] = _clamp(key, manual.get(key, outputs.get(key)))
            forced.append(key)

    if forced:
        return " | FORCED " + ",".join(forced)
    return ""




def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _vfd_speed_command_pct(settings: Dict[str, Any]) -> float:
    if "vfd_speed_command_pct" in settings:
        return clamp(_safe_float(settings.get("vfd_speed_command_pct"), 100.0), 0.0, 100.0)
    legacy_volts = _safe_float(settings.get("vfd_speed_command_volts", getattr(const, "vfd_speed_command_volts", 10.0)), 10.0)
    default_pct = _safe_float(getattr(const, "vfd_speed_command_pct", legacy_volts * 10.0), legacy_volts * 10.0)
    return clamp(default_pct, 0.0, 100.0)


def _track_alert(
    alarm_key: str,
    ts_key: str,
    expected: float,
    measured: float,
    tolerance: float,
    timeout_s: float,
    alarms: Dict[str, Any],
    activation_ts: Dict[str, Any],
    now: float,
) -> None:
    if abs(expected - measured) <= tolerance:
        activation_ts[ts_key] = 0.0
        alarms[alarm_key] = False
        return

    if activation_ts.get(ts_key, 0.0) == 0.0:
        activation_ts[ts_key] = now
        return

    if (now - activation_ts.get(ts_key, 0.0)) >= timeout_s:
        alarms[alarm_key] = True


def _pid_pool(shared_state) -> Dict[str, PIDController]:
    pool = shared_state.get("_pid_controllers")
    if not isinstance(pool, dict):
        pool = {}
        shared_state["_pid_controllers"] = pool
    return pool


def _pid_params_changed(pid: PIDController, kp: float, ki: float, kd: float, setpoint: float, limits: Tuple[float, float], deadband: float) -> bool:
    return (
        pid.Kp != kp
        or pid.Ki != ki
        or pid.Kd != kd
        or pid.setpoint != setpoint
        or pid.output_limits != limits
        or pid.deadband != deadband
    )


def _get_pid(
    shared_state,
    key: str,
    kp: float,
    ki: float,
    kd: float,
    setpoint: float,
    output_limits: Tuple[float, float],
    initial_output: float,
    sample_time: float,
    deadband: float,
    output_step: float,
    max_delta: float,
    direction: str,
) -> PIDController:
    pool = _pid_pool(shared_state)
    pid = pool.get(key)
    if pid is None:
        pid = PIDController(
            kp,
            ki,
            kd,
            setpoint,
            sample_time=sample_time,
            output_limits=output_limits,
            initial_output=initial_output,
            deadband=deadband,
            output_step=output_step,
            max_delta=max_delta,
            direction=direction,
            name=key,
        )
        pool[key] = pid
        return pid

    if _pid_params_changed(pid, kp, ki, kd, setpoint, output_limits, deadband):
        pid.Kp = kp
        pid.Ki = ki
        pid.Kd = kd
        pid.setpoint = setpoint
        pid.output_limits = output_limits
        pid.deadband = deadband
    pid.sample_time = sample_time
    pid.output_step = output_step
    pid.max_delta_output = max_delta
    pid.set_direction(direction)
    return pid


def _valve_pid_command(shared_state, now: float, ret_t: float, sp_t: float) -> float:
    actuators = shared_state.get("actuators") or {}
    activation_ts = shared_state.get("activation_ts") or {}
    settings = shared_state.get("settings") or {}

    hold_s = max(5.0, _safe_float(settings.get("valve_min_output_hold_time_seconds", getattr(const, "valve_min_output_hold_time_seconds", 30.0)), 30.0))
    kp = _safe_float(settings.get("valve_pid_kp", getattr(const, "valve_pid_kp", 1.2)), 1.2)
    ki = _safe_float(settings.get("valve_pid_ki", getattr(const, "valve_pid_ki", 0.0)), 0.0)
    kd = _safe_float(settings.get("valve_pid_kd", getattr(const, "valve_pid_kd", 0.0)), 0.0)
    deadband = _safe_float(settings.get("valve_deadband_c", getattr(const, "valve_deadband_c", 0.2)), 0.2)
    output_step = _safe_float(settings.get("valve_pid_output_step", getattr(const, "valve_pid_output_step", 0.1)), 0.1)
    max_delta = _safe_float(settings.get("valve_pid_max_delta", getattr(const, "valve_pid_max_delta", 10.0)), 10.0)
    current_valve = _safe_float(actuators.get("control_valvula", 0.0), 0.0)

    pid = _get_pid(
        shared_state,
        "valve",
        kp,
        ki,
        kd,
        sp_t,
        (0.0, 10.0),
        current_valve,
        0.0,
        deadband,
        output_step,
        max_delta,
        "reverse",
    )
    desired_valve = pid.update(ret_t)
    if desired_valve is None:
        desired_valve = current_valve

    last_ts = activation_ts.get("_valve_hold_ts", 0.0)
    if last_ts == 0.0 or (now - last_ts) >= hold_s:
        activation_ts["_valve_hold_ts"] = now
        return clamp(desired_valve, 0.0, 10.0)
    return current_valve


def _pid_output(shared_state, key: str, params: Dict[str, float], setpoint: float, measured: float, output_max: float, direction: str = "direct") -> float:
    pid = _get_pid(
        shared_state,
        key,
        float(params.get("kp", 0.0)),
        float(params.get("ki", 0.0)),
        float(params.get("kd", 0.0)),
        setpoint,
        (0.0, output_max),
        0.0,
        0.0,
        0.0,
        0.1,
        output_max,
        direction,
    )
    output = pid.update(measured)
    return 0.0 if output is None else clamp(output, 0.0, output_max)


def _run_tipico_1_2(shared_state, now: float) -> None:
    sensors = shared_state.get("sensors")
    actuators = shared_state.get("actuators")
    alarms = shared_state.get("alarms")
    activation_ts = shared_state.get("activation_ts")
    settings = shared_state.get("settings")
    setpoints = shared_state.get("setpoints")

    if sensors is None:
        sensors = {}
    if actuators is None:
        actuators = {}
    if alarms is None:
        alarms = {}
    if activation_ts is None:
        activation_ts = {}
    if settings is None:
        settings = {}
    if setpoints is None:
        setpoints = {}

    tipico_id = int(shared_state.get("tipico", tipicos.DEFAULT_TIPICO))
    cfg = tipicos.get_tipico_config(tipico_id)
    features = cfg.get("features", {})

    validation = tipicos.validate_tipico_runtime(tipico_id, dict(sensors), dict(actuators))
    if validation["missing_sensors"] or validation["missing_actuators"]:
        _log(
            f"[control] tipico={tipico_id} faltantes sensores={sorted(validation['missing_sensors'])} "
            f"actuadores={sorted(validation['missing_actuators'])}"
        )

    on_global = bool(shared_state.get("on_off_global", True))
    smoke = bool(sensors.get("detector_humo", 0))
    thermal = bool(sensors.get("alarma_termica", 0))
    vfd_alarm = bool(sensors.get("alarma_vfd", 0))
    supply_high_temp_fault = _supply_high_temp_fault(sensors, alarms, activation_ts, settings, now)
    fan_fb = bool(sensors.get("estatus_ventilador", 0))

    pos_manual = bool(sensors.get("posicion_manual", 0))
    pos_auto = bool(sensors.get("posicion_automatico", 1))

    ret_t = _safe_float(sensors.get("temperatura_retorno", 0.0))
    sp_t = _safe_float(setpoints.get("temperature", 20.0), 20.0)
    valve_fb = _safe_float(sensors.get("retroalimentacion_valvula", 0.0))
    vfd_fb = _safe_float(sensors.get("frecuencia_vfd", 0.0))

    fan_timeout = _safe_float(settings.get("fan_feedback_timeout_seconds", 45.0), 45.0)
    tracking_tol = _safe_float(settings.get("feedback_tolerance_volts", 1.0), 1.0)
    valve_tracking_timeout = _safe_float(settings.get("valve_tracking_timeout_seconds", 60.0), 60.0)
    vfd_tracking_timeout = _safe_float(settings.get("vfd_tracking_timeout_seconds", 60.0), 60.0)

    # PID genérico de válvula con hold-time mínimo.
    valve_cmd = _valve_pid_command(shared_state, now, ret_t, sp_t)

    run_request = on_global and pos_auto
    if features.get("usa_auto_manual", False) and pos_manual:
        alarms["interlock_manual"] = True
        run_request = False
        valve_cmd = 0.0
    else:
        alarms["interlock_manual"] = False

    if smoke:
        alarms["interlock_humo"] = True
        run_request = False
    else:
        alarms["interlock_humo"] = False

    if thermal and features.get("usa_contactor", False):
        alarms["interlock_termica"] = True
        run_request = False
    else:
        alarms["interlock_termica"] = False

    if vfd_alarm and features.get("usa_vfd", False):
        alarms["interlock_vfd"] = True
        run_request = False
    else:
        alarms["interlock_vfd"] = False

    if supply_high_temp_fault:
        run_request = False

    # Confirmación de ventilador
    if run_request and not fan_fb:
        if activation_ts.get("ventilador", 0.0) == 0.0:
            activation_ts["ventilador"] = now
        elif (now - activation_ts.get("ventilador", 0.0)) >= fan_timeout:
            alarms["alerta_ventilador"] = True
            run_request = False
    else:
        activation_ts["ventilador"] = 0.0
        if fan_fb:
            alarms["alerta_ventilador"] = False

    if not run_request:
        valve_cmd = 0.0

    cmd_contactor = bool(run_request and features.get("usa_contactor", False))
    cmd_vfd = bool(run_request and features.get("usa_vfd", False))
    vfd_sp = _vfd_speed_command_pct(settings) if cmd_vfd else 0.0
    valve_cmd = clamp(valve_cmd if run_request else 0.0, 0.0, 10.0)

    outputs = {
        "comando_contactor": cmd_contactor,
        "comando_vfd": cmd_vfd,
        "control_frec_vfd": vfd_sp,
        "control_valvula": valve_cmd,
    }

    forced_info = _apply_forced_outputs_for_tipico(shared_state, outputs, tipico_id)

    # Reaplicar bloqueos de seguridad (humo, térmica, VFD alarm)
    if smoke or thermal or supply_high_temp_fault:
        _apply_total_fault_shutdown(outputs)
    elif vfd_alarm and features.get("usa_vfd", False):
        outputs["comando_vfd"] = False
        outputs["control_frec_vfd"] = 0.0

    valve_cmd = outputs.get("control_valvula", 0.0)
    vfd_sp = outputs.get("control_frec_vfd", 0.0)

    _track_alert(
        "alerta_tracking_valvula",
        "tracking_valvula",
        valve_cmd,
        valve_fb,
        tracking_tol,
        valve_tracking_timeout,
        alarms,
        activation_ts,
        now,
    )

    if features.get("usa_vfd", False):
        _track_alert(
            "alerta_tracking_vfd",
            "tracking_vfd",
            vfd_sp,
            vfd_fb,
            tracking_tol,
            vfd_tracking_timeout,
            alarms,
            activation_ts,
            now,
        )

    actuators["comando_contactor"] = outputs["comando_contactor"]
    actuators["comando_vfd"] = outputs["comando_vfd"]
    actuators["control_frec_vfd"] = outputs["control_frec_vfd"]
    actuators["control_valvula"] = outputs["control_valvula"]

    # espejo legado para mantener compatibilidad con otros módulos
    actuators["fan"] = bool(outputs["comando_contactor"] or outputs["comando_vfd"])
    sensors["fan_status"] = int(fan_fb)
    sensors["return_temp"] = ret_t
    if forced_info:
        activation_ts["_forced_info"] = forced_info


def _run_tipico_vfd_valve(shared_state, now: float, features: Dict[str, Any]) -> None:
    """
    Control para típicos basados en VFD + válvula + (opcional) UV, dámper OA y heater.
    Cubre: 3, 5, 6, 8, 11.
    """
    sensors = shared_state.get("sensors") or {}
    actuators = shared_state.get("actuators") or {}
    alarms = shared_state.get("alarms") or {}
    activation_ts = shared_state.get("activation_ts") or {}
    settings = shared_state.get("settings") or {}
    setpoints = shared_state.get("setpoints") or {}

    tipico_id = int(shared_state.get("tipico", tipicos.DEFAULT_TIPICO))
    on_global = bool(shared_state.get("on_off_global", True))
    smoke = bool(sensors.get("detector_humo", 0))
    vfd_alarm = bool(sensors.get("alarma_vfd", 0))
    supply_high_temp_fault = _supply_high_temp_fault(sensors, alarms, activation_ts, settings, now)
    fan_fb = bool(sensors.get("estatus_ventilador", 0))
    uv_status = bool(sensors.get("estatus_luz_ultravioleta", 0))

    alarms["interlock_humo"] = smoke
    alarms["interlock_vfd"] = vfd_alarm

    ret_t = _safe_float(sensors.get("temperatura_retorno", 0.0), 0.0)
    sp_t = _safe_float(setpoints.get("temperature", 20.0), 20.0)

    run_request = on_global and not smoke and not supply_high_temp_fault

    # Fan / VFD commands
    vfd_cmd = run_request and not vfd_alarm
    vfd_sp = _vfd_speed_command_pct(settings) if vfd_cmd else 0.0

    # PID genérico de válvula.
    valve_cmd = _valve_pid_command(shared_state, now, ret_t, sp_t)

    # Fan feedback confirmation
    fan_timeout = _safe_float(settings.get("fan_feedback_timeout_seconds", 45.0), 45.0)
    if run_request and not fan_fb:
        if activation_ts.get("ventilador", 0.0) == 0.0:
            activation_ts["ventilador"] = now
        elif (now - activation_ts.get("ventilador", 0.0)) >= fan_timeout:
            alarms["alerta_ventilador"] = True
            run_request = False
    else:
        activation_ts["ventilador"] = 0.0
        if fan_fb:
            alarms["alerta_ventilador"] = False

    # UV control
    uv_cmd = False
    if features.get("usa_uv", False):
        uv_cmd = bool(run_request and fan_fb)
        uv_timeout = _safe_float(settings.get("uv_status_timeout_seconds", getattr(const, "uv_status_timeout_seconds", 20.0)), 20.0)
        if uv_cmd:
            if uv_status:
                activation_ts["uv"] = 0.0
                alarms["alerta_uv"] = False
            else:
                if activation_ts.get("uv", 0.0) == 0.0:
                    activation_ts["uv"] = now
                elif now - activation_ts.get("uv", 0.0) >= uv_timeout:
                    alarms["alerta_uv"] = True
        else:
            activation_ts["uv"] = 0.0
            alarms["alerta_uv"] = False
    else:
        alarms["alerta_uv"] = False
        activation_ts["uv"] = 0.0

    # Heater PID
    heater_max_auto = clamp(_safe_float(settings.get("heater_max_pct", getattr(const, "heater_max_pct", HEATER_MAX)), HEATER_MAX), 0.0, HEATER_MAX)
    heater_pct = 0.0
    if features.get("usa_heater", False) and run_request:
        heater_error = sp_t - ret_t  # >0 necesita calentar
        heater_pct = _pid_output(shared_state, "heat", PID_HEAT, sp_t, ret_t, heater_max_auto, "direct")
        if heater_error <= 0:
            heater_pct = 0.0
            _pid_pool(shared_state).pop("heat", None)
        heater_pct = clamp(heater_pct, 0.0, heater_max_auto)
    else:
        _pid_pool(shared_state).pop("heat", None)
        heater_pct = 0.0

    # OA damper
    damper_voltage = 0.0
    if features.get("usa_oa_damper", False):
        v_on = _safe_float(settings.get("oa_damper_voltage_on", getattr(const, "oa_damper_voltage_on", 10.0)), 10.0)
        v_off = _safe_float(settings.get("oa_damper_voltage_off", getattr(const, "oa_damper_voltage_off", 0.0)), 0.0)
        damper_voltage = v_on if run_request else v_off

    outputs = {
        "comando_vfd": bool(vfd_cmd),
        "control_frec_vfd": vfd_sp,
        "control_valvula": valve_cmd if run_request else 0.0,
        "control_compuerta_aire_exterior": damper_voltage,
        "comando_luz_ultravioleta": uv_cmd,
        "heater": heater_pct,
    }

    forced_info = _apply_forced_outputs_for_tipico(shared_state, outputs, tipico_id)

    # Reaplicar bloqueos de seguridad
    if smoke or supply_high_temp_fault:
        _apply_total_fault_shutdown(outputs)
    elif vfd_alarm:
        outputs["comando_vfd"] = False
        outputs["control_frec_vfd"] = 0.0

    valve_cmd = outputs.get("control_valvula", 0.0)
    vfd_sp = outputs.get("control_frec_vfd", 0.0)

    # VFD-valve tracking alert usando comandos finales
    if outputs.get("comando_vfd", False):
        tol = _safe_float(settings.get("valve_vfd_track_tol", getattr(const, "valve_vfd_track_tol", 0.8)), 0.8)
        timeout_track = _safe_float(settings.get("valve_vfd_track_timeout_seconds", getattr(const, "valve_vfd_track_timeout_seconds", 20.0)), 20.0)
        diff = abs(valve_cmd - _safe_float(sensors.get("frecuencia_vfd", 0.0), 0.0))
        if diff > tol:
            if activation_ts.get("tracking_vfd_valvula", 0.0) == 0.0:
                activation_ts["tracking_vfd_valvula"] = now
            elif now - activation_ts.get("tracking_vfd_valvula", 0.0) >= timeout_track:
                alarms["alerta_tracking_vfd_valvula"] = True
        else:
            activation_ts["tracking_vfd_valvula"] = 0.0
            alarms["alerta_tracking_vfd_valvula"] = False
    else:
        activation_ts["tracking_vfd_valvula"] = 0.0
        alarms["alerta_tracking_vfd_valvula"] = False

    actuators["comando_vfd"] = outputs["comando_vfd"]
    actuators["control_frec_vfd"] = outputs["control_frec_vfd"]
    actuators["control_valvula"] = outputs["control_valvula"]
    actuators["control_compuerta_aire_exterior"] = outputs.get("control_compuerta_aire_exterior", 0.0)
    actuators["comando_luz_ultravioleta"] = outputs.get("comando_luz_ultravioleta", False)
    actuators["heater"] = outputs.get("heater", 0.0)

    actuators["fan"] = bool(outputs.get("comando_vfd", False))
    sensors["fan_status"] = int(fan_fb)
    sensors["return_temp"] = ret_t
    if forced_info:
        activation_ts["_forced_info"] = forced_info


def _run_tipico_contactor_valve(shared_state, now: float, features: Dict[str, Any]) -> None:
    """
    Control para típicos con contactor + válvula + heater (+ opcional UV y dámper OA).
    Cubre: 7 y 12.
    """
    sensors = shared_state.get("sensors") or {}
    actuators = shared_state.get("actuators") or {}
    alarms = shared_state.get("alarms") or {}
    activation_ts = shared_state.get("activation_ts") or {}
    settings = shared_state.get("settings") or {}
    setpoints = shared_state.get("setpoints") or {}

    on_global = bool(shared_state.get("on_off_global", True))
    pos_manual = bool(sensors.get("posicion_manual", 0))
    pos_auto = bool(sensors.get("posicion_automatico", 1))
    smoke = bool(sensors.get("detector_humo", 0))
    thermal = bool(sensors.get("alarma_termica", 0))
    supply_high_temp_fault = _supply_high_temp_fault(sensors, alarms, activation_ts, settings, now)
    fan_fb = bool(sensors.get("estatus_ventilador", 0))
    uv_status = bool(sensors.get("estatus_luz_ultravioleta", 0))

    alarms["interlock_humo"] = smoke
    alarms["interlock_termica"] = thermal

    ret_t = _safe_float(sensors.get("temperatura_retorno", 0.0), 0.0)
    sp_t = _safe_float(setpoints.get("temperature", 20.0), 20.0)

    run_request = on_global and pos_auto and not smoke and not thermal and not supply_high_temp_fault
    if features.get("usa_auto_manual", False) and pos_manual:
        alarms["interlock_manual"] = True
        run_request = False
    else:
        alarms["interlock_manual"] = False

    # PID genérico de válvula.
    valve_cmd = _valve_pid_command(shared_state, now, ret_t, sp_t)

    # Fan feedback confirmation
    fan_timeout = _safe_float(settings.get("fan_feedback_timeout_seconds", 45.0), 45.0)
    if run_request and not fan_fb:
        if activation_ts.get("ventilador", 0.0) == 0.0:
            activation_ts["ventilador"] = now
        elif (now - activation_ts.get("ventilador", 0.0)) >= fan_timeout:
            alarms["alerta_ventilador"] = True
            run_request = False
    else:
        activation_ts["ventilador"] = 0.0
        if fan_fb:
            alarms["alerta_ventilador"] = False

    # Heater PID
    heater_max_auto = clamp(_safe_float(settings.get("heater_max_pct", getattr(const, "heater_max_pct", HEATER_MAX)), HEATER_MAX), 0.0, HEATER_MAX)
    heater_pct = 0.0
    if features.get("usa_heater", False) and run_request:
        heater_error = sp_t - ret_t
        heater_pct = _pid_output(shared_state, "heat", PID_HEAT, sp_t, ret_t, heater_max_auto, "direct")
        if heater_error <= 0:
            heater_pct = 0.0
            _pid_pool(shared_state).pop("heat", None)
        heater_pct = clamp(heater_pct, 0.0, heater_max_auto)
    else:
        _pid_pool(shared_state).pop("heat", None)
        heater_pct = 0.0

    # OA damper
    damper_voltage = 0.0
    if features.get("usa_oa_damper", False):
        v_on = _safe_float(settings.get("oa_damper_voltage_on", getattr(const, "oa_damper_voltage_on", 10.0)), 10.0)
        v_off = _safe_float(settings.get("oa_damper_voltage_off", getattr(const, "oa_damper_voltage_off", 0.0)), 0.0)
        damper_voltage = v_on if run_request else v_off

    # UV (solo típico 12)
    uv_cmd = False
    if features.get("usa_uv", False):
        uv_cmd = bool(run_request and fan_fb)
        uv_timeout = _safe_float(settings.get("uv_status_timeout_seconds", getattr(const, "uv_status_timeout_seconds", 20.0)), 20.0)
        if uv_cmd:
            if uv_status:
                activation_ts["uv"] = 0.0
                alarms["alerta_uv"] = False
            else:
                if activation_ts.get("uv", 0.0) == 0.0:
                    activation_ts["uv"] = now
                elif now - activation_ts.get("uv", 0.0) >= uv_timeout:
                    alarms["alerta_uv"] = True
        else:
            activation_ts["uv"] = 0.0
            alarms["alerta_uv"] = False
    else:
        activation_ts["uv"] = 0.0
        alarms["alerta_uv"] = False

    outputs = {
        "comando_contactor": bool(run_request),
        "control_valvula": valve_cmd if run_request else 0.0,
        "control_compuerta_aire_exterior": damper_voltage,
        "comando_luz_ultravioleta": uv_cmd,
        "heater": heater_pct,
    }

    forced_info = _apply_forced_outputs_for_tipico(shared_state, outputs, shared_state.get("tipico", tipicos.DEFAULT_TIPICO))

    # Apagados de seguridad (no bypass)
    if smoke or thermal or supply_high_temp_fault:
        _apply_total_fault_shutdown(outputs)

    actuators["comando_contactor"] = outputs["comando_contactor"]
    actuators["control_valvula"] = outputs["control_valvula"]
    actuators["control_compuerta_aire_exterior"] = outputs.get("control_compuerta_aire_exterior", 0.0)
    actuators["comando_luz_ultravioleta"] = outputs.get("comando_luz_ultravioleta", False)
    actuators["heater"] = outputs.get("heater", 0.0)

    actuators["fan"] = bool(outputs["comando_contactor"])
    sensors["fan_status"] = int(fan_fb)
    sensors["return_temp"] = ret_t
    if forced_info:
        activation_ts["_forced_info"] = forced_info

def control_loop(shared_state, stop_event, period_seconds: float = 2.0) -> None:
    """
    Lógica principal:
    - AUTO: lazos PID para demanda de frío (temp/hum) -> etapas de compresor, y PID de calor.
    - MANUAL: aplica overrides.
    """
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except Exception:
        pass
    # Forzar primer escritura: arrancamos sin últimos outputs conocidos
    last_outputs: Dict[str, Any] = {}
    last_stage = 0
    cycle_state: Dict[str, Dict[str, float]] = {}
    last_stage = last_stage
    startup_ts = None
    stage1_on_ts = None
    comp_start_anchor = time.time()
    comp_start_delay_released = False

    while not stop_event.is_set():
        try:
            alarms = shared_state.get("alarms") or {}
            activation_ts = shared_state.get("activation_ts") or {}
            sensors = shared_state.get("sensors") or {}
            setpoints = shared_state.get("setpoints") or {}
            settings = shared_state.get("settings") or {}

            now = time.time()
            if not comp_start_delay_released and (now - comp_start_anchor) >= FIRST_COMP_START_DELAY:
                comp_start_delay_released = True

            heater_max_auto = _refresh_runtime_params(shared_state)
            tipico_id = int(shared_state.get("tipico", tipicos.DEFAULT_TIPICO))
            if tipico_id in (1, 2):
                _run_tipico_1_2(shared_state, now)
                time.sleep(period_seconds)
                continue
            if tipico_id in (3, 5, 6, 8, 11):
                _run_tipico_vfd_valve(shared_state, now, tipicos.get_tipico_config(tipico_id).get("features", {}))
                time.sleep(period_seconds)
                continue
            if tipico_id in (7, 12):
                _run_tipico_contactor_valve(shared_state, now, tipicos.get_tipico_config(tipico_id).get("features", {}))
                time.sleep(period_seconds)
                continue

            enabled = bool(shared_state.get("on_off_global", True))
            supply_high_temp_fault = _supply_high_temp_fault(sensors, alarms, activation_ts, settings, now)
            if not enabled:
                outputs = {"fan": False, "heater": 0.0}
                info = "OFF"
                for k in activation_ts.keys():
                    activation_ts[k] = 0.0
                startup_ts = None
                stage1_on_ts = None
                last_stage = 0
            else:
                if startup_ts is None:
                    startup_ts = now
                mode = str(shared_state.get("mode", "AUTO")).upper()
                startup_elapsed = now - startup_ts

                if mode == "MANUAL":
                    outputs, info = _manual_outputs(shared_state)
                elif startup_elapsed < STARTUP_DELAY:
                    outputs = {"fan": True, "heater": 0.0}
                    info = f"STARTUP {startup_elapsed:.0f}/{STARTUP_DELAY:.0f}s"
                else:
                    temp_sp = float(setpoints.get("temperature", 20.0))
                    return_temp = float(sensors.get("return_temp", 0.0))

                    temp_error_hot = return_temp - temp_sp       # >0 necesita enfriar
                    humidity_error = 0.0
                    temp_demand_pct = 0.0
                    hum_demand_pct = 0.0
                    cooling_demand_pct = 0.0

                    if CONTROL_MODE == "TEMP_HUM":
                        humidity = float(sensors.get("humidity", 0.0))
                        hum_sp = float(setpoints.get("humidity", 60.0))
                        humidity_error = humidity - hum_sp
                        hum_demand_pct = _pid_output(shared_state, "hum", PID_HUM, hum_sp, humidity, 100.0, "reverse")
                        if humidity_error <= 0:
                            hum_demand_pct = 0.0
                            _pid_pool(shared_state).pop("hum", None)

                    if CONTROL_MODE == "TEMP_HUM":
                        temp_demand_pct = _pid_output(shared_state, "temp", PID_TEMP, temp_sp, return_temp, 100.0, "reverse")
                        if temp_error_hot <= 0:
                            temp_demand_pct = 0.0
                            _pid_pool(shared_state).pop("temp", None)
                        cooling_demand_pct = max(temp_demand_pct, hum_demand_pct)
                        desired_stage = _stage_from_pid_demand(cooling_demand_pct, last_stage)
                    else:
                        # Staging por error con histéresis (TEMP_ONLY se mantiene igual)
                        temp_stage = 0
                        if temp_error_hot >= TEMP_STAGE2_DELTA:
                            temp_stage = 2
                        elif temp_error_hot >= TEMP_STAGE1_DELTA:
                            temp_stage = 1

                        hum_stage = 0
                        if CONTROL_MODE == "TEMP_HUM":
                            if humidity_error >= HUM_STAGE2_DELTA:
                                hum_stage = 2
                            elif humidity_error >= HUM_STAGE1_DELTA:
                                hum_stage = 1

                        temp_stage2_off_threshold = temp_sp - TEMP_STAGE2_OFF_DELTA
                        temp_stage1_off_threshold = temp_sp - TEMP_STAGE1_OFF_DELTA

                        if last_stage == 2:
                            temp_stage = 2 if return_temp > temp_stage2_off_threshold else 1
                        else:
                            temp_stage = 2 if temp_error_hot >= TEMP_STAGE2_DELTA else temp_stage

                        if temp_stage < 1:
                            if last_stage >= 1:
                                temp_stage = 1 if return_temp > temp_stage1_off_threshold else 0
                            else:
                                temp_stage = 1 if temp_error_hot >= TEMP_STAGE1_DELTA else 0

                        desired_stage = max(temp_stage, hum_stage)

                    if desired_stage >= 1 and last_stage == 0:
                        stage1_on_ts = now
                    if desired_stage >= 2:
                        if stage1_on_ts is None or (now - stage1_on_ts) < STAGE2_DELAY:
                            desired_stage = 1
                    if desired_stage == 0:
                        stage1_on_ts = None

                    stage = desired_stage
                    last_stage = stage

                    heater_pct = 0.0
                    if CONTROL_MODE == "TEMP_HUM":
                        # Reheat: usar temp + componente de humedad cuando hay deshumidificación activa
                        heater_error_base = temp_sp - return_temp  # >0 necesita calentar
                        heater_error = heater_error_base
                        if humidity_error > 0 and cooling_demand_pct > 0 and REHEAT_HUM_GAIN > 0:
                            heater_error += humidity_error * REHEAT_HUM_GAIN
                        heater_sp = temp_sp + (humidity_error * REHEAT_HUM_GAIN if humidity_error > 0 and cooling_demand_pct > 0 and REHEAT_HUM_GAIN > 0 else 0.0)
                        heater_pct = _pid_output(shared_state, "heat", PID_HEAT, heater_sp, return_temp, HEATER_MAX, "direct")
                        if heater_error <= 0:
                            heater_pct = 0.0
                            _pid_pool(shared_state).pop("heat", None)
                        heater_pct = clamp(heater_pct, 0.0, heater_max_auto)

                    info_extra = ""
                    if not comp_start_delay_released:
                        remaining = int(max(0, FIRST_COMP_START_DELAY - (now - comp_start_anchor)))
                        info_extra += f" | COMP START DELAY {remaining}s"

                    outputs = {
                        "fan": True,
                        "heater": heater_pct,
                    }

                    if CONTROL_MODE == "TEMP_HUM":
                        info = (
                            f"AUTO[{CONTROL_MODE}] stage={stage} "
                            f"cool={cooling_demand_pct:.1f}% eT={temp_error_hot:.2f} eH={humidity_error:.2f} "
                            f"heat={heater_pct:.1f}{info_extra}"
                        )
                    else:
                        info = (
                            f"AUTO[{CONTROL_MODE}] stage={stage} "
                            f"eT={temp_error_hot:.2f} eH={humidity_error:.2f} heat={heater_pct:.1f}{info_extra}"
                        )

                # Overrides forzados por dispositivo
                info += _apply_forced(shared_state, outputs)

                # Aplicar bloqueos por alarmas
                if alarms.get("fan"):
                    outputs["fan"] = False
                    outputs["heater"] = 0.0
                    info += " | FAN ALARM"
                else:
                    if alarms.get("heater"):
                        outputs["heater"] = 0.0
                        info += " | HEATER ALARM"

                # Si el ventilador está apagado, forzar calentador a OFF
                if not outputs.get("fan", False):
                    outputs["heater"] = 0.0
                else:
                    pass

            if supply_high_temp_fault:
                _apply_total_fault_shutdown(outputs)
                info += " | INTERLOCK TEMP SUM ALTA"

            heater_forced = bool((shared_state.get("manual_overrides") or {}).get("heater_forced", False))

            # Suavizado de bajada para heater (no aplica si está forzado)
            if CONTROL_MODE == "TEMP_HUM" and HEATER_SLEW_DOWN > 0 and not heater_forced:
                prev_heater = float(last_outputs.get("heater", outputs.get("heater", 0.0)))
                target_heater = float(outputs.get("heater", 0.0))
                if target_heater < prev_heater:
                    max_drop = HEATER_SLEW_DOWN * period_seconds
                    outputs["heater"] = max(target_heater, prev_heater - max_drop)


            # Verificar confirmaciones de estado (30s)
            def _check(key: str, command_on: bool, status_value: Any, timeout_enabled: bool = True):
                if not command_on:
                    activation_ts[key] = 0.0
                    return
                if alarms.get(key):
                    activation_ts[key] = 0.0
                    return
                if bool(status_value):
                    activation_ts[key] = 0.0
                    return
                if not timeout_enabled:
                    activation_ts[key] = 0.0
                    return
                if activation_ts.get(key, 0.0) == 0.0:
                    activation_ts[key] = now
                    return
                if now - activation_ts.get(key, 0.0) >= STATUS_TIMEOUT:
                    alarms[key] = True
                    activation_ts[key] = 0.0
                    # Apagar dispositivo con alarma
                    if key == "fan":
                        outputs["fan"] = False
                        outputs["heater"] = 0.0
                    elif key == "heater":
                        outputs["heater"] = 0.0
                    _log(f"[control] ALARMA {key.upper()}: sin confirmación en {STATUS_TIMEOUT}s")

            _check("fan", outputs.get("fan", False), sensors.get("fan_status", 0))
            _check("heater", outputs.get("heater", 0) >= HEATER_ALARM_PCT, sensors.get("heater_status", 0))

            actuators = shared_state.get("actuators")
            if actuators is not None:
                for key, value in outputs.items():
                    actuators[key] = value
                """ print(
                    f"[control] {info} | Tret={sensors.get('return_temp', 0):.2f}C "
                    f"Ts= {sensors.get('supply_temp', 0):.2f}C Hum={sensors.get('humidity', 0):.1f}% "
                    f"SP_T={setpoints.get('temperature', 0)} SP_H={setpoints.get('humidity', 0)} | "
                    f"fan={outputs['fan']} heater={outputs['heater']:.1f} "
                    f"| alarms: fan={alarms.get('fan')} heater={alarms.get('heater')}"
                ) """
                last_outputs = outputs

        except Exception as exc:  # pragma: no cover - protección en runtime
            _log(f"[control] Error en ciclo de control: {exc}")

        time.sleep(period_seconds)
