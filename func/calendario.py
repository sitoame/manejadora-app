"""
Calendario operativo para habilitar/deshabilitar la manejadora.

Configuracion:
    Editar solo la seccion "CONFIGURACION DEL CALENDARIO".

Referencia IEC 61131-3:
    El modulo usa una estructura de Function Block con variables EN, Q, PT y
    ET, y temporizadores tipo TON/TOF para retardos de encendido/apagado.
    El resultado se publica en shared_state["calendar"].
"""

import json
import signal
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

try:
    from var import const
except Exception:  # pragma: no cover
    const = None


# ---------------------------------------------------------------------------
# CONFIGURACION DEL CALENDARIO
# ---------------------------------------------------------------------------

# Habilita la participacion del calendario en la habilitacion efectiva.
# El modulo solo reporta estado en shared_state["calendar"].
CALENDARIO_HABILITADO = True

# Zona horaria local del controlador.
ZONA_HORARIA = "America/Panama"

# Periodo de evaluacion del calendario.
CICLO_SEGUNDOS = 10.0

# Retardos estilo IEC 61131-3:
# - TON: la salida Q pasa a ON cuando la solicitud lleva PT segundos activa.
# - TOF: la salida Q se mantiene ON durante PT segundos luego de quitar la solicitud.
RETARDO_ENCENDIDO_SEG = 0.0
RETARDO_APAGADO_SEG = 0.0

# Estado aplicado si no hay ningun horario activo.
ESTADO_FUERA_DE_HORARIO = False

# Horario semanal. Por seguridad operativa, el valor inicial mantiene el
# comportamiento actual: programa habilitado 24/7. Cambiar aqui los rangos.
#
# Formato:
#   "LUN": [("06:00", "18:00"), ("20:00", "23:00")]
#   "SAB": []  # apagado todo el dia
#   ("22:00", "06:00") cruza medianoche.
#   Para dia completo usar ("00:00", "24:00").
HORARIO_SEMANAL: Dict[str, List[Tuple[str, str]]] = {
    "LUN": [("00:00", "24:00")],
    "MAR": [("00:00", "24:00")],
    "MIE": [("00:00", "24:00")],
    "JUE": [("00:00", "24:00")],
    "VIE": [("00:00", "24:00")],
    "SAB": [("00:00", "24:00")],
    "DOM": [("00:00", "24:00")],
}

# Excepciones por fecha. Tienen prioridad sobre HORARIO_SEMANAL.
#
# Valores permitidos:
#   False                         -> apagado todo el dia
#   True                          -> encendido todo el dia
#   [("08:00", "12:00"), ...]     -> horario especial de ese dia
EXCEPCIONES_FECHA: Dict[str, Any] = {
    # "2026-01-01": False,
    # "2026-12-24": [("08:00", "12:00")],
}

# Eventos con prioridad maxima. Util para mantenimiento o encendidos puntuales.
#
# Formato de fecha/hora: "YYYY-MM-DD HH:MM" o "YYYY-MM-DDTHH:MM".
EVENTOS_PRIORITARIOS: List[Dict[str, Any]] = [
    # {
    #     "nombre": "mantenimiento",
    #     "desde": "2026-06-10 14:00",
    #     "hasta": "2026-06-10 16:00",
    #     "estado": False,
    # },
]


# Archivo usado por la API /api/horario para persistir cambios sin editar el
# codigo Python en caliente. Los valores de arriba siguen siendo defaults.
_HORARIO_PATH = Path(getattr(const, "horario_config_file", "var/horario.json"))
if not _HORARIO_PATH.is_absolute():
    _HORARIO_PATH = Path(__file__).resolve().parent.parent / _HORARIO_PATH
HORARIO_CONFIG_FILE = _HORARIO_PATH


# ---------------------------------------------------------------------------
# IMPLEMENTACION
# ---------------------------------------------------------------------------

DIAS_IEC = {
    "LUN": 0,
    "MAR": 1,
    "MIE": 2,
    "JUE": 3,
    "VIE": 4,
    "SAB": 5,
    "DOM": 6,
}
DIAS_POR_INDICE = {v: k for k, v in DIAS_IEC.items()}


@dataclass(frozen=True)
class ResultadoCalendario:
    enabled: bool
    request: bool
    q: bool
    source: str
    detail: str
    now_local: str


class TON:
    """Temporizador ON-delay con nombres de variables IEC 61131-3."""

    def __init__(self, pt_seconds: float = 0.0):
        self.PT = max(0.0, float(pt_seconds))
        self.IN = False
        self.Q = False
        self.ET = 0.0
        self._start_ts: Optional[float] = None

    def update(self, in_value: bool, now_ts: float) -> bool:
        self.IN = bool(in_value)
        if not self.IN:
            self._start_ts = None
            self.ET = 0.0
            self.Q = False
            return self.Q

        if self._start_ts is None:
            self._start_ts = now_ts
        self.ET = max(0.0, now_ts - self._start_ts)
        self.Q = self.ET >= self.PT
        return self.Q


class TOF:
    """Temporizador OFF-delay con nombres de variables IEC 61131-3."""

    def __init__(self, pt_seconds: float = 0.0):
        self.PT = max(0.0, float(pt_seconds))
        self.IN = False
        self.Q = False
        self.ET = 0.0
        self._off_ts: Optional[float] = None

    def update(self, in_value: bool, now_ts: float) -> bool:
        self.IN = bool(in_value)
        if self.IN:
            self._off_ts = None
            self.ET = 0.0
            self.Q = True
            return self.Q

        if self._off_ts is None:
            self._off_ts = now_ts
        self.ET = max(0.0, now_ts - self._off_ts)
        self.Q = self.ET < self.PT
        return self.Q


class FB_Calendario:
    """Function Block principal del calendario."""

    def __init__(
        self,
        en: bool = CALENDARIO_HABILITADO,
        ton_pt: float = RETARDO_ENCENDIDO_SEG,
        tof_pt: float = RETARDO_APAGADO_SEG,
    ):
        self.EN = bool(en)
        self.Q = False
        self.REQ = False
        self.ton_encendido = TON(ton_pt)
        self.tof_apagado = TOF(tof_pt)

    def sync_config(self) -> None:
        self.EN = bool(CALENDARIO_HABILITADO)
        self.ton_encendido.PT = max(0.0, float(RETARDO_ENCENDIDO_SEG))
        self.tof_apagado.PT = max(0.0, float(RETARDO_APAGADO_SEG))

    def update(self, now: Optional[datetime] = None) -> ResultadoCalendario:
        self.sync_config()
        now_local = now or _now_local()
        request, source, detail = evaluar_solicitud(now_local)
        self.REQ = bool(request)

        if not self.EN:
            self.Q = False
            return ResultadoCalendario(
                enabled=False,
                request=self.REQ,
                q=self.Q,
                source="DISABLED",
                detail="calendario deshabilitado",
                now_local=now_local.isoformat(timespec="seconds"),
            )

        now_ts = now_local.timestamp()
        q_ton = self.ton_encendido.update(self.REQ, now_ts)
        self.Q = self.tof_apagado.update(q_ton, now_ts)

        return ResultadoCalendario(
            enabled=True,
            request=self.REQ,
            q=self.Q,
            source=source,
            detail=detail,
            now_local=now_local.isoformat(timespec="seconds"),
        )


def _timezone():
    if ZoneInfo is None:
        return None
    try:
        return ZoneInfo(ZONA_HORARIA)
    except Exception:
        return None


def _now_local() -> datetime:
    tz = _timezone()
    if tz is None:
        return datetime.now().astimezone()
    return datetime.now(tz)


def _parse_seconds(value: str) -> int:
    text = str(value).strip()
    parts = text.split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"hora invalida: {value!r}")

    hour = int(parts[0])
    minute = int(parts[1])
    second = int(parts[2]) if len(parts) == 3 else 0

    if hour == 24 and minute == 0 and second == 0:
        return 24 * 60 * 60
    if hour < 0 or hour > 23 or minute < 0 or minute > 59 or second < 0 or second > 59:
        raise ValueError(f"hora fuera de rango: {value!r}")
    return hour * 3600 + minute * 60 + second


def _parse_intervals(raw_intervals: Iterable[Tuple[str, str]]) -> List[Tuple[int, int]]:
    intervals = []
    for start, end in raw_intervals:
        intervals.append((_parse_seconds(start), _parse_seconds(end)))
    return intervals


def _seconds_of_day(now: datetime) -> int:
    return now.hour * 3600 + now.minute * 60 + now.second


def _is_active_today(now: datetime, intervals: Iterable[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
    sec = _seconds_of_day(now)
    for start, end in intervals:
        if end > start and start <= sec < end:
            return start, end
        if end < start and sec >= start:
            return start, end
        if start == 0 and end == 24 * 60 * 60:
            return start, end
    return None


def _is_active_from_previous_day(now: datetime, intervals: Iterable[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
    sec = _seconds_of_day(now)
    for start, end in intervals:
        if end < start and sec < end:
            return start, end
    return None


def _format_interval(interval: Tuple[int, int]) -> str:
    def fmt(seconds: int) -> str:
        if seconds == 24 * 60 * 60:
            return "24:00"
        hour = seconds // 3600
        minute = (seconds % 3600) // 60
        return f"{hour:02d}:{minute:02d}"

    return f"{fmt(interval[0])}-{fmt(interval[1])}"


def _normalizar_dia(dia: Any) -> Optional[str]:
    if isinstance(dia, int):
        return DIAS_POR_INDICE.get(dia)
    text = str(dia).strip().upper()
    return text if text in DIAS_IEC else None


def _intervalos_semanales(dia_index: int) -> List[Tuple[int, int]]:
    dia_key = DIAS_POR_INDICE.get(dia_index)
    if not dia_key:
        return []
    raw = HORARIO_SEMANAL.get(dia_key, [])
    return _parse_intervals(raw)


def _intervalos_excepcion(fecha: str) -> Optional[List[Tuple[int, int]]]:
    if fecha not in EXCEPCIONES_FECHA:
        return None
    value = EXCEPCIONES_FECHA.get(fecha)
    if value is True:
        return [(0, 24 * 60 * 60)]
    if value is False or value is None:
        return []
    return _parse_intervals(value)


def _parse_datetime(value: Any) -> datetime:
    text = str(value).strip().replace(" ", "T", 1)
    dt = datetime.fromisoformat(text)
    tz = _timezone()
    if dt.tzinfo is None and tz is not None:
        dt = dt.replace(tzinfo=tz)
    elif dt.tzinfo is not None and tz is not None:
        dt = dt.astimezone(tz)
    return dt


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("1", "true", "on", "yes", "si"):
            return True
        if text in ("0", "false", "off", "no"):
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _as_non_negative_float(value: Any, field_name: str) -> float:
    try:
        out = float(value)
    except Exception as exc:
        raise ValueError(f"{field_name} debe ser numerico") from exc
    if out < 0:
        raise ValueError(f"{field_name} no puede ser negativo")
    return out


def _validate_timezone(value: Any) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("zona_horaria no puede estar vacia")
    if ZoneInfo is not None:
        try:
            ZoneInfo(text)
        except Exception as exc:
            raise ValueError(f"zona_horaria invalida: {text}") from exc
    return text


def _normalize_interval_pair(raw: Any) -> Tuple[str, str]:
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        raise ValueError(f"intervalo invalido: {raw!r}")
    start = str(raw[0]).strip()
    end = str(raw[1]).strip()
    _parse_seconds(start)
    _parse_seconds(end)
    return start, end


def _normalize_intervals(raw_intervals: Any) -> List[Tuple[str, str]]:
    if raw_intervals is None:
        return []
    if not isinstance(raw_intervals, list):
        raise ValueError("los intervalos deben ser una lista")
    return [_normalize_interval_pair(item) for item in raw_intervals]


def _normalize_weekly(raw_weekly: Any, base: Optional[Dict[str, Any]] = None) -> Dict[str, List[Tuple[str, str]]]:
    if not isinstance(raw_weekly, dict):
        raise ValueError("horario_semanal debe ser un objeto")

    out: Dict[str, List[Tuple[str, str]]] = {}
    src_base = base or HORARIO_SEMANAL
    for day_key in DIAS_IEC.keys():
        out[day_key] = _normalize_intervals(list(src_base.get(day_key, [])))

    for raw_day, raw_intervals in raw_weekly.items():
        day_key = _normalizar_dia(raw_day)
        if day_key is None:
            raise ValueError(f"dia invalido en horario_semanal: {raw_day!r}")
        out[day_key] = _normalize_intervals(raw_intervals)
    return out


def _normalize_exceptions(raw_exceptions: Any) -> Dict[str, Any]:
    if raw_exceptions is None:
        return {}
    if not isinstance(raw_exceptions, dict):
        raise ValueError("excepciones_fecha debe ser un objeto")

    out: Dict[str, Any] = {}
    for raw_date, value in raw_exceptions.items():
        date_key = str(raw_date).strip()
        try:
            datetime.fromisoformat(date_key)
        except Exception as exc:
            raise ValueError(f"fecha invalida en excepciones_fecha: {date_key!r}") from exc

        if isinstance(value, bool) or value is None:
            out[date_key] = value
        else:
            out[date_key] = _normalize_intervals(value)
    return out


def _normalize_events(raw_events: Any) -> List[Dict[str, Any]]:
    if raw_events is None:
        return []
    if not isinstance(raw_events, list):
        raise ValueError("eventos_prioritarios debe ser una lista")

    events: List[Dict[str, Any]] = []
    for item in raw_events:
        if not isinstance(item, dict):
            raise ValueError(f"evento invalido: {item!r}")
        start = _parse_datetime(item.get("desde"))
        end = _parse_datetime(item.get("hasta"))
        if end <= start:
            raise ValueError("cada evento debe tener hasta mayor que desde")
        events.append(
            {
                "nombre": str(item.get("nombre", "evento_prioritario")),
                "desde": str(item.get("desde")),
                "hasta": str(item.get("hasta")),
                "estado": _as_bool(item.get("estado", item.get("state", False)), False),
            }
        )
    return events


def _intervals_for_json(intervals: Iterable[Tuple[str, str]]) -> List[List[str]]:
    return [[str(start), str(end)] for start, end in intervals]


def get_horario_config(load_file: bool = False) -> Dict[str, Any]:
    if load_file:
        load_horario_config_file()

    return {
        "calendario_habilitado": bool(CALENDARIO_HABILITADO),
        "zona_horaria": ZONA_HORARIA,
        "ciclo_segundos": float(CICLO_SEGUNDOS),
        "retardo_encendido_seg": float(RETARDO_ENCENDIDO_SEG),
        "retardo_apagado_seg": float(RETARDO_APAGADO_SEG),
        "estado_fuera_de_horario": bool(ESTADO_FUERA_DE_HORARIO),
        "horario_semanal": {
            day: _intervals_for_json(HORARIO_SEMANAL.get(day, []))
            for day in DIAS_IEC.keys()
        },
        "excepciones_fecha": {
            date_key: (
                _intervals_for_json(value)
                if isinstance(value, list)
                else value
            )
            for date_key, value in EXCEPCIONES_FECHA.items()
        },
        "eventos_prioritarios": [dict(event) for event in EVENTOS_PRIORITARIOS],
        "archivo": str(HORARIO_CONFIG_FILE),
    }


def apply_horario_config(payload: Dict[str, Any], persist: bool = False) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload_must_be_object")

    global CALENDARIO_HABILITADO, ZONA_HORARIA, CICLO_SEGUNDOS
    global RETARDO_ENCENDIDO_SEG, RETARDO_APAGADO_SEG, ESTADO_FUERA_DE_HORARIO
    global HORARIO_SEMANAL, EXCEPCIONES_FECHA, EVENTOS_PRIORITARIOS

    if "enabled" in payload and "calendario_habilitado" not in payload:
        payload["calendario_habilitado"] = payload["enabled"]
    if "timezone" in payload and "zona_horaria" not in payload:
        payload["zona_horaria"] = payload["timezone"]
    if "cycle_seconds" in payload and "ciclo_segundos" not in payload:
        payload["ciclo_segundos"] = payload["cycle_seconds"]
    if "on_delay_seconds" in payload and "retardo_encendido_seg" not in payload:
        payload["retardo_encendido_seg"] = payload["on_delay_seconds"]
    if "off_delay_seconds" in payload and "retardo_apagado_seg" not in payload:
        payload["retardo_apagado_seg"] = payload["off_delay_seconds"]
    if "default_outside_schedule" in payload and "estado_fuera_de_horario" not in payload:
        payload["estado_fuera_de_horario"] = payload["default_outside_schedule"]
    if "weekly" in payload and "horario_semanal" not in payload:
        payload["horario_semanal"] = payload["weekly"]
    if "exceptions" in payload and "excepciones_fecha" not in payload:
        payload["excepciones_fecha"] = payload["exceptions"]
    if "priority_events" in payload and "eventos_prioritarios" not in payload:
        payload["eventos_prioritarios"] = payload["priority_events"]

    if "calendario_habilitado" in payload:
        CALENDARIO_HABILITADO = _as_bool(payload.get("calendario_habilitado"), CALENDARIO_HABILITADO)
    if "zona_horaria" in payload:
        ZONA_HORARIA = _validate_timezone(payload.get("zona_horaria"))
    if "ciclo_segundos" in payload:
        CICLO_SEGUNDOS = max(0.25, _as_non_negative_float(payload.get("ciclo_segundos"), "ciclo_segundos"))
    if "retardo_encendido_seg" in payload:
        RETARDO_ENCENDIDO_SEG = _as_non_negative_float(
            payload.get("retardo_encendido_seg"),
            "retardo_encendido_seg",
        )
    if "retardo_apagado_seg" in payload:
        RETARDO_APAGADO_SEG = _as_non_negative_float(
            payload.get("retardo_apagado_seg"),
            "retardo_apagado_seg",
        )
    if "estado_fuera_de_horario" in payload:
        ESTADO_FUERA_DE_HORARIO = _as_bool(
            payload.get("estado_fuera_de_horario"),
            ESTADO_FUERA_DE_HORARIO,
        )
    if "horario_semanal" in payload:
        HORARIO_SEMANAL = _normalize_weekly(payload.get("horario_semanal"))
    if "excepciones_fecha" in payload:
        EXCEPCIONES_FECHA = _normalize_exceptions(payload.get("excepciones_fecha"))
    if "eventos_prioritarios" in payload:
        EVENTOS_PRIORITARIOS = _normalize_events(payload.get("eventos_prioritarios"))

    snapshot = get_horario_config(load_file=False)
    if persist:
        save_horario_config(snapshot)
    return snapshot


def save_horario_config(snapshot: Optional[Dict[str, Any]] = None) -> None:
    payload = snapshot or get_horario_config(load_file=False)
    HORARIO_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = HORARIO_CONFIG_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(HORARIO_CONFIG_FILE)


def load_horario_config_file() -> bool:
    if not HORARIO_CONFIG_FILE.exists():
        return False
    with HORARIO_CONFIG_FILE.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    apply_horario_config(payload, persist=False)
    return True


def _evento_prioritario(now: datetime) -> Optional[Tuple[bool, str]]:
    for event in EVENTOS_PRIORITARIOS:
        try:
            start = _parse_datetime(event.get("desde"))
            end = _parse_datetime(event.get("hasta"))
            if start <= now < end:
                name = str(event.get("nombre", "evento_prioritario"))
                return bool(event.get("estado", False)), name
        except Exception as exc:
            return False, f"evento invalido: {exc}"
    return None


def evaluar_solicitud(now: Optional[datetime] = None) -> Tuple[bool, str, str]:
    """Devuelve solicitud cruda del calendario antes de TON/TOF."""

    now_local = now or _now_local()

    event = _evento_prioritario(now_local)
    if event is not None:
        state, name = event
        return state, "EVENTO", name

    today = now_local.date()
    today_key = today.isoformat()
    today_exception = _intervalos_excepcion(today_key)

    if today_exception is not None:
        active = _is_active_today(now_local, today_exception)
        if active is not None:
            return True, "EXCEPCION_FECHA", f"{today_key} {_format_interval(active)}"
        return ESTADO_FUERA_DE_HORARIO, "EXCEPCION_FECHA", f"{today_key} fuera de horario"

    yesterday_key = (today - timedelta(days=1)).isoformat()
    yesterday_exception = _intervalos_excepcion(yesterday_key)
    if yesterday_exception is not None:
        active_prev = _is_active_from_previous_day(now_local, yesterday_exception)
        if active_prev is not None:
            return True, "EXCEPCION_FECHA", f"{yesterday_key} {_format_interval(active_prev)}"

    today_intervals = _intervalos_semanales(now_local.weekday())
    active_today = _is_active_today(now_local, today_intervals)
    if active_today is not None:
        dia = _normalizar_dia(now_local.weekday()) or str(now_local.weekday())
        return True, "SEMANAL", f"{dia} {_format_interval(active_today)}"

    prev_day = (now_local.weekday() - 1) % 7
    prev_intervals = _intervalos_semanales(prev_day)
    active_prev = _is_active_from_previous_day(now_local, prev_intervals)
    if active_prev is not None:
        dia = _normalizar_dia(prev_day) or str(prev_day)
        return True, "SEMANAL", f"{dia} {_format_interval(active_prev)}"

    return ESTADO_FUERA_DE_HORARIO, "FUERA_DE_HORARIO", "sin intervalo activo"


def _publish_result(shared_state, result: ResultadoCalendario) -> None:
    calendar_state = shared_state.get("calendar")
    if calendar_state is None:
        calendar_state = {}
        shared_state["calendar"] = calendar_state

    calendar_state["enabled"] = bool(result.enabled)
    calendar_state["request"] = bool(result.request)
    calendar_state["q"] = bool(result.q)
    calendar_state["source"] = result.source
    calendar_state["detail"] = result.detail
    calendar_state["now_local"] = result.now_local
    calendar_state["timezone"] = ZONA_HORARIA
    calendar_state["cycle_seconds"] = float(CICLO_SEGUNDOS)
    calendar_state["on_delay_seconds"] = float(RETARDO_ENCENDIDO_SEG)
    calendar_state["off_delay_seconds"] = float(RETARDO_APAGADO_SEG)
    calendar_state["ts"] = time.time()


def apply_calendar_once(shared_state) -> ResultadoCalendario:
    try:
        load_horario_config_file()
    except Exception as exc:
        print(f"[calendario] No se pudo cargar horario inicial: {exc}", flush=True)

    fb = FB_Calendario()
    result = fb.update()
    _publish_result(shared_state, result)
    return result


def calendario_loop(shared_state, stop_event) -> None:
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except Exception:
        pass

    fb = FB_Calendario()
    last_q: Optional[bool] = None
    last_detail = ""
    last_config_mtime: Optional[float] = None

    while not stop_event.is_set():
        try:
            if HORARIO_CONFIG_FILE.exists():
                mt = HORARIO_CONFIG_FILE.stat().st_mtime
                if last_config_mtime is None or mt > last_config_mtime:
                    load_horario_config_file()
                    last_config_mtime = mt
                    print(f"[calendario] Configuracion cargada desde {HORARIO_CONFIG_FILE}", flush=True)

            result = fb.update()
            _publish_result(shared_state, result)

            if last_q is None or last_q != result.q or last_detail != result.detail:
                print(
                    f"[calendario] Q={result.q} REQ={result.request} "
                    f"source={result.source} detail={result.detail}",
                    flush=True,
                )
                last_q = result.q
                last_detail = result.detail
        except Exception as exc:
            print(f"[calendario] Error: {exc}", flush=True)

        stop_event.wait(max(0.25, float(CICLO_SEGUNDOS)))
