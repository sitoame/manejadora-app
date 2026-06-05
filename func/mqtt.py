import json
import signal
import threading
import time
from typing import Dict, Any
from pathlib import Path

import paho.mqtt.client as mqtt

try:
    from var import const
except Exception:  # pragma: no cover - defensivo
    const = None

try:
    from var import tipicos
except Exception:  # pragma: no cover - defensivo
    tipicos = None

BROKER = getattr(const, "mqtt_broker", "181.78.120.121")
PORT = getattr(const, "mqtt_port", 1883)
TOPIC_CMD = getattr(const, "mqtt_topic_cmd", "manejadora_david")
TOPIC_STATUS = getattr(const, "mqtt_topic_status", "manejadora_david_status")
CLIENT_ID = getattr(const, "controller_id", "eg628_david")
USERNAME = getattr(const, "mqtt_username", None)
PASSWORD = getattr(const, "mqtt_password", None)
STATUS_INTERVAL = getattr(const, "mqtt_status_interval", 30)
MQTT_ENABLED_DEFAULT = getattr(const, "mqtt_enabled", True)
MQTT_RECONNECT_SECONDS = getattr(const, "mqtt_reconnect_seconds", 5)
SETPOINTS_FILE = Path(getattr(const, "setpoints_file", "logs/setpoints.json"))


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str) -> None:
    print(f"[mqtt {_now()}] {msg}")


def _update_manual(shared_state, overrides: Dict[str, Any]) -> None:
    manual = shared_state.get("manual_overrides")
    if manual is None:
        return
    for key in ("fan",):
        if key in overrides:
            manual[key] = bool(overrides[key])
    if "heater" in overrides:
        try:
            manual["heater"] = float(overrides["heater"])
        except Exception:
            manual["heater"] = 0.0


def _force_device(shared_state, device: str, value: Any) -> None:
    manual = shared_state.get("manual_overrides")
    if manual is None:
        return
    manual[device] = value
    manual[f"{device}_forced"] = True


def _auto_device(shared_state, device: str) -> None:
    manual = shared_state.get("manual_overrides")
    if manual is None:
        return
    manual[f"{device}_forced"] = False


def _clear_all_forced(shared_state) -> None:
    manual = shared_state.get("manual_overrides")
    if manual is None:
        return
    for k in (
        "fan",
        "heater",
        "comando_contactor",
        "comando_vfd",
        "control_frec_vfd",
        "control_valvula",
        "control_compuerta_aire_exterior",
        "comando_luz_ultravioleta",
    ):
        manual[f"{k}_forced"] = False


def _force_ao(shared_state, device: str, value: Any, max_val: float = 10.0) -> None:
    try:
        v = float(value)
    except Exception:
        v = 0.0
    v = max(0.0, min(max_val, v))
    _force_device(shared_state, device, v)


def _auto_override(shared_state, device: str) -> None:
    _auto_device(shared_state, device)


def _tipico_features(shared_state) -> Dict[str, Any]:
    if not tipicos:
        return {}
    try:
        tipico_id = int(shared_state.get("tipico", getattr(tipicos, "DEFAULT_TIPICO", 1)))
        return dict(tipicos.get_tipico_config(tipico_id).get("features", {}))
    except Exception:
        return {}


def _fan_command_key(shared_state) -> str:
    features = _tipico_features(shared_state)
    if features.get("usa_vfd", False):
        return "comando_vfd"
    if features.get("usa_contactor", False):
        return "comando_contactor"
    return "fan"


def _is_manual(shared_state) -> bool:
    return str(shared_state.get("mode", "AUTO")).upper() == "MANUAL"


def _require_manual(shared_state, cmd: str) -> bool:
    return True


def _reset_alarms(shared_state) -> None:
    alarms = shared_state.get("alarms")
    activation_ts = shared_state.get("activation_ts")
    if alarms is not None:
        for k in alarms.keys():
            alarms[k] = False
    if activation_ts is not None:
        for k in activation_ts.keys():
            activation_ts[k] = 0.0


def _reset_alarm_group(shared_state, group: str) -> None:
    alarms = shared_state.get("alarms")
    activation_ts = shared_state.get("activation_ts")
    sensors = shared_state.get("sensors") or {}
    group = str(group).lower()

    alarm_groups = {
        "fan": {"fan", "alerta_ventilador", "interlock_vfd", "alerta_tracking_vfd", "alerta_tracking_vfd_valvula"},
        "valvula": {"alerta_tracking_valvula", "alerta_tracking_vfd_valvula"},
        "heater": {"heater"},
        "humo": {"interlock_humo"},
    }
    ts_groups = {
        "fan": {"fan", "ventilador", "tracking_vfd", "tracking_vfd_valvula"},
        "valvula": {"tracking_valvula", "tracking_vfd_valvula"},
        "heater": {"heater"},
        "humo": set(),
    }

    if group == "humo" and bool(sensors.get("detector_humo", 0)):
        _log("RESET_HUMO ignorado: detector_humo sigue activo")
        return

    if alarms is not None:
        for key in alarm_groups.get(group, set()):
            if key in alarms:
                alarms[key] = False
    if activation_ts is not None:
        for key in ts_groups.get(group, set()):
            if key in activation_ts:
                activation_ts[key] = 0.0
    _pulse_reset(shared_state, group)


def _persist_setpoints(shared_state) -> None:
    setpoints = shared_state.get("setpoints") or {}
    payload = {
        "temperature": float(setpoints.get("temperature", 0.0)),
        "humidity": float(setpoints.get("humidity", 0.0)),
        "ts": time.time(),
    }
    try:
        SETPOINTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = SETPOINTS_FILE.with_suffix(".json.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        tmp_path.replace(SETPOINTS_FILE)
    except Exception as exc:
        _log(f"No se pudo persistir setpoints: {exc}")


def _pulse_reset(shared_state, key: str, duration: float = 2.0) -> None:
    resets = shared_state.get("resets")
    if resets is None:
        return
    resets[key] = 1

    def _clear():
        resets[key] = 0

    timer = threading.Timer(duration, _clear)
    timer.daemon = True
    timer.start()


def apply_command(shared_state, payload: Dict[str, Any]) -> None:
    """
    Procesa comandos recibidos por MQTT.
    Comandos soportados:
      - SET_TEMP / SETPOINT_TEMP / SETPOINT_TEMPERATURA -> value (float)
      - SET_HUM / SETPOINT_HUM / SETPOINT_HUMEDAD -> value (float)
      - POWER / ON_OFF -> value (bool/int)
      - MODE / MODO -> AUTO o MANUAL
      - MANUAL / MODO_MANUAL -> overrides de salidas forzables (fan, heater, contactor, VFD DO/AO, válvula, dámper, UV) y marca *_forced
      - FORCE_FAN_ON / FORCE_FAN_OFF / AUTO_FAN -> forzar/auto ventilador o VFD DO si el típico usa VFD
      - FORCE_FAN_VEL / AUTO_FAN_VEL -> forzar/auto velocidad VFD en 0-100 %
      - FORCE_HEATER (value 0-100) / AUTO_HEATER -> forzar/auto calentador
      - AUTO_ALL / AUTO_GLOBAL -> quita todos los forzados y pone modo AUTO
      - RESET_ALARMS / CLEAR_ALARMS -> limpia todas las alarmas y reinicia contadores
      - RESET_FAN / RESET_HEATER -> limpia alarmas específicas
    """
    target = payload.get("controller")
    if target and str(target).upper() != str(CLIENT_ID).upper():
        _log(f"Ignorando comando para '{target}', este cliente es '{CLIENT_ID}'")
        return

    cmd = str(payload.get("command", "")).upper()
    value = payload.get("value")
    setpoints = shared_state.get("setpoints")

    if cmd in ("SET_TEMP", "SETPOINT_TEMP", "SETPOINT_TEMPERATURA"):
        try:
            setpoints["temperature"] = float(value)
            _log(f"SET_TEMP -> {setpoints['temperature']}")
            _persist_setpoints(shared_state)
        except Exception:
            pass
    elif cmd in ("SET_HUM", "SETPOINT_HUM", "SETPOINT_HUMEDAD"):
        try:
            setpoints["humidity"] = float(value)
            _log(f"SET_HUM -> {setpoints['humidity']}")
            _persist_setpoints(shared_state)
        except Exception:
            pass
    elif cmd in ("POWER", "ON_OFF", "ENCENDIDO"):
        state_val = bool(value)
        shared_state["on_off_global"] = state_val
        _log(f"POWER -> {state_val}")
    elif cmd in ("SET_TIPICO", "TIPICO"):
        try:
            shared_state["tipico"] = int(value)
            _log(f"TIPICO -> {shared_state['tipico']}")
        except Exception:
            _log(f"TIPICO inválido: {value}")
    elif cmd in ("SET_VFD_SPEED", "VFD_SPEED"):
        settings = shared_state.get("settings")
        if settings is not None:
            try:
                speed_pct = max(0.0, min(100.0, float(value)))
            except Exception:
                speed_pct = 0.0
            settings["vfd_speed_command_pct"] = speed_pct
            _log(f"SET_VFD_SPEED -> {speed_pct:.1f}%")
    elif cmd in ("MODE", "MODO"):
        if value:
            mode_value = str(value).upper()
            shared_state["mode"] = mode_value
            if mode_value == "AUTO":
                _clear_all_forced(shared_state)
                _log("Cambiando a AUTO: limpiando forzados")
            else:
                _log(f"MODE -> {mode_value}")
    elif cmd in ("MANUAL", "MODO_MANUAL"):
        overrides = payload.get("overrides") or value or {}
        if not overrides:
            # Si no se envían overrides, toma los outputs actuales como punto de partida
            current_outputs = shared_state.get("actuators") or {}
            overrides = {
                "fan": current_outputs.get("fan", False),
                "heater": current_outputs.get("heater", 0.0),
                "comando_contactor": current_outputs.get("comando_contactor", False),
                "comando_vfd": current_outputs.get("comando_vfd", False),
                "control_frec_vfd": current_outputs.get("control_frec_vfd", 0.0),
                "control_valvula": current_outputs.get("control_valvula", 0.0),
                "control_compuerta_aire_exterior": current_outputs.get("control_compuerta_aire_exterior", 0.0),
                "comando_luz_ultravioleta": current_outputs.get("comando_luz_ultravioleta", False),
            }
        manual = shared_state.get("manual_overrides")
        if manual is not None:
            for k, v in overrides.items():
                if k in {"control_valvula", "control_compuerta_aire_exterior"}:
                    try:
                        manual[k] = max(0.0, min(10.0, float(v)))
                    except Exception:
                        manual[k] = 0.0
                elif k in {"heater", "control_frec_vfd"}:
                    try:
                        manual[k] = max(0.0, min(100.0, float(v)))
                    except Exception:
                        manual[k] = 0.0
                else:
                    manual[k] = bool(v)
                manual[f"{k}_forced"] = True
        shared_state["mode"] = "MANUAL"
        _log(f"MODO MANUAL activado con overrides {overrides}")
    elif cmd in ("FORCE_FAN_ON", "FAN_ON"):
        if not _require_manual(shared_state, cmd):
            return
        fan_key = _fan_command_key(shared_state)
        _force_device(shared_state, fan_key, True)
        _log(f"Forzado FAN = ON ({fan_key})")
    elif cmd in ("FORCE_FAN_OFF", "FAN_OFF"):
        if not _require_manual(shared_state, cmd):
            return
        fan_key = _fan_command_key(shared_state)
        _force_device(shared_state, fan_key, False)
        _log(f"Forzado FAN = OFF ({fan_key})")
    elif cmd in ("AUTO_FAN", "RESET_FORCE_FAN"):
        if not _require_manual(shared_state, cmd):
            return
        fan_key = _fan_command_key(shared_state)
        _auto_device(shared_state, fan_key)
        _auto_device(shared_state, "fan")
        _log(f"FAN en AUTO ({fan_key})")
    elif cmd in ("FORCE_FAN_VEL", "FORCE_FAN_SPEED", "FAN_VEL", "FAN_SPEED"):
        if not _require_manual(shared_state, cmd):
            return
        _force_ao(shared_state, "control_frec_vfd", value, 100.0)
        _log(f"Forzado FAN_VEL = {shared_state.get('manual_overrides', {}).get('control_frec_vfd', 0.0):.1f}%")
    elif cmd in ("AUTO_FAN_VEL", "AUTO_FAN_SPEED", "RESET_FORCE_FAN_VEL"):
        if not _require_manual(shared_state, cmd):
            return
        _auto_override(shared_state, "control_frec_vfd")
        _log("FAN_VEL en AUTO")
    elif cmd == "FORCE_HEATER":
        if not _require_manual(shared_state, cmd):
            return
        try:
            heater_value = float(payload.get("value", 0.0))
        except Exception:
            heater_value = 0.0
        heater_value = max(0.0, min(100.0, heater_value))
        _force_device(shared_state, "heater", heater_value)
        _log(f"Forzado HEATER = {heater_value:.1f}%")
    elif cmd == "AUTO_HEATER":
        if not _require_manual(shared_state, cmd):
            return
        _auto_device(shared_state, "heater")
        _log("HEATER en AUTO")
    elif cmd in ("FORCE_VALVE", "VALVE_SET"):
        if not _require_manual(shared_state, cmd):
            return
        _force_ao(shared_state, "control_valvula", value, 10.0)
        _log(f"Forzado VALVULA = {shared_state.get('manual_overrides', {}).get('control_valvula', 0.0):.2f} V")
    elif cmd == "AUTO_VALVE":
        _auto_override(shared_state, "control_valvula")
        _log("VALVULA en AUTO")
    elif cmd in ("FORCE_VFD_DO_ON", "VFD_DO_ON"):
        _force_device(shared_state, "comando_vfd", True)
        _log("Forzado COMANDO_VFD = ON")
    elif cmd in ("FORCE_VFD_DO_OFF", "VFD_DO_OFF"):
        _force_device(shared_state, "comando_vfd", False)
        _log("Forzado COMANDO_VFD = OFF")
    elif cmd == "AUTO_VFD_DO":
        _auto_override(shared_state, "comando_vfd")
        _log("COMANDO_VFD en AUTO")
    elif cmd in ("FORCE_VFD_AO", "FORCE_VFD_FREQ"):
        _force_ao(shared_state, "control_frec_vfd", value, 100.0)
        _log(f"Forzado FREC_VFD = {shared_state.get('manual_overrides', {}).get('control_frec_vfd', 0.0):.1f}%")
    elif cmd == "AUTO_VFD_AO":
        _auto_override(shared_state, "control_frec_vfd")
        _log("FREC_VFD en AUTO")
    elif cmd in ("FORCE_CONTACTOR_ON", "CONTACTOR_ON"):
        _force_device(shared_state, "comando_contactor", True)
        _log("Forzado CONTACTOR = ON")
    elif cmd in ("FORCE_CONTACTOR_OFF", "CONTACTOR_OFF"):
        _force_device(shared_state, "comando_contactor", False)
        _log("Forzado CONTACTOR = OFF")
    elif cmd == "AUTO_CONTACTOR":
        _auto_override(shared_state, "comando_contactor")
        _log("CONTACTOR en AUTO")
    elif cmd == "FORCE_DAMPER":
        _force_ao(shared_state, "control_compuerta_aire_exterior", value, 10.0)
        _log(f"Forzado DAMPER = {shared_state.get('manual_overrides', {}).get('control_compuerta_aire_exterior', 0.0):.2f} V")
    elif cmd == "AUTO_DAMPER":
        _auto_override(shared_state, "control_compuerta_aire_exterior")
        _log("DAMPER en AUTO")
    elif cmd in ("FORCE_UV_ON", "UV_ON"):
        _force_device(shared_state, "comando_luz_ultravioleta", True)
        _log("Forzado UV = ON")
    elif cmd in ("FORCE_UV_OFF", "UV_OFF"):
        _force_device(shared_state, "comando_luz_ultravioleta", False)
        _log("Forzado UV = OFF")
    elif cmd == "AUTO_UV":
        _auto_override(shared_state, "comando_luz_ultravioleta")
        _log("UV en AUTO")
    elif cmd in ("AUTO_ALL", "AUTO_GLOBAL"):
        _clear_all_forced(shared_state)
        shared_state["mode"] = "AUTO"
        _log("AUTO global: limpiando forzados y volviendo a AUTO")
    elif cmd in ("RESET_FORCE_ALL", "AUTO_FORCE_ALL"):
        _clear_all_forced(shared_state)
        _log("Forzados limpiados")
    elif cmd in ("RESET_ALARMS", "CLEAR_ALARMS", "RESET_ALARMAS"):
        _reset_alarms(shared_state)
        _log("RESET_ALARMS")
    elif cmd in ("RESET_CMD_FAN", "RESET_CMD_HEATER", "RESET_CMD_ALL"):
        keymap = {
            "RESET_CMD_FAN": "fan",
            "RESET_CMD_HEATER": "heater",
            "RESET_CMD_ALL": "all",
        }
        target = keymap.get(cmd)
        if target:
            _pulse_reset(shared_state, target)
            _log(f"{cmd} -> 1 (pulso)")
    elif cmd in ("RESET_FAN", "RESET_HEATER", "RESET_VALVE", "RESET_VALVULA", "RESET_HUMO", "RESET_SMOKE"):
        keymap = {
            "RESET_FAN": "fan",
            "RESET_HEATER": "heater",
            "RESET_VALVE": "valvula",
            "RESET_VALVULA": "valvula",
            "RESET_HUMO": "humo",
            "RESET_SMOKE": "humo",
        }
        target_key = keymap.get(cmd, "")
        _reset_alarm_group(shared_state, target_key)
        _log(f"{cmd}")
    elif cmd == "SET_ALARMS":
        alarms = shared_state.get("alarms")
        if alarms is not None:
            for k, v in (payload.get("alarms") or {}).items():
                if k in alarms:
                    alarms[k] = bool(v)
            _log(f"SET_ALARMS -> {payload.get('alarms')}")
    else:
        _log(f"Mensaje no aceptado: comando desconocido '{cmd}' payload={payload}")


def publish_status(client: mqtt.Client, shared_state) -> None:
    try:
        payload = {
            "controller": CLIENT_ID,
            "on_off_global": bool(shared_state.get("on_off_global", True)),
            "mode": shared_state.get("mode", "AUTO"),
            "setpoints": dict(shared_state.get("setpoints", {})),
            "outputs": dict(shared_state.get("actuators", {})),
            "sensors": dict(shared_state.get("sensors", {})),
        }
        client.publish(TOPIC_STATUS, json.dumps(payload), qos=0, retain=False)
    except Exception as exc:  # pragma: no cover - runtime
        _log(f"No se pudo publicar estado: {exc}")


def on_connect(client, userdata, flags, rc):
    _log(f"Conectado ({rc}) broker={BROKER}:{PORT}, suscribiendo a {TOPIC_CMD}")
    client.subscribe(TOPIC_CMD)


def on_message(client, userdata, msg):
    shared_state = userdata.get("shared_state")
    raw = ""
    try:
        raw = msg.payload.decode("utf-8")
        _log(f"RX topic={msg.topic} payload={raw}")
        payload = json.loads(raw)
    except Exception as exc:
        _log(f"Mensaje no aceptado: error decodificando ({exc}) payload={raw}")
        return

    if not isinstance(payload, dict):
        _log(f"Mensaje no aceptado: payload no es dict -> {payload}")
        return

    try:
        apply_command(shared_state, payload)
    except Exception as exc:
        _log(f"Error procesando comando: {exc} payload={payload}")


def on_disconnect(client, userdata, rc):
    _log(f"Desconectado del broker (rc={rc})")


def mqtt_loop(shared_state, stop_event) -> None:
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except Exception:
        pass

    # Usa client_id aleatorio para evitar expulsión por colisión con otros clientes
    client = mqtt.Client(client_id=None)
    if USERNAME:
        client.username_pw_set(USERNAME, PASSWORD)
    client.user_data_set({"shared_state": shared_state})
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.reconnect_delay_set(min_delay=MQTT_RECONNECT_SECONDS, max_delay=MQTT_RECONNECT_SECONDS)

    mqtt_started = False
    last_status = 0.0

    while not stop_event.is_set():
        try:
            settings = shared_state.get("settings") or {}
            mqtt_enabled = bool(settings.get("mqtt_enabled", MQTT_ENABLED_DEFAULT))
            status_interval = float(settings.get("mqtt_status_interval_seconds", STATUS_INTERVAL))

            if mqtt_enabled and not mqtt_started:
                _log(f"MQTT habilitado. Conectando a {BROKER}:{PORT}")
                client.connect_async(BROKER, PORT, 60)
                client.loop_start()
                mqtt_started = True
                last_status = 0.0

            if (not mqtt_enabled) and mqtt_started:
                _log("MQTT desactivado en runtime_config.json")
                try:
                    client.loop_stop()
                    client.disconnect()
                except Exception:
                    pass
                mqtt_started = False
                time.sleep(1)
                continue

            if mqtt_started:
                now = time.time()
                if status_interval > 0 and now - last_status >= status_interval:
                    publish_status(client, shared_state)
                    last_status = now

            time.sleep(1)

        except Exception as exc:
            _log(f"Error en loop MQTT: {exc}")
            time.sleep(2)

    if mqtt_started:
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass
