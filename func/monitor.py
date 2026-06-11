import base64
import json
import signal
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Any, List
from urllib.parse import urlparse, parse_qs

import os

from func import calendario, runtime_config
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

MONITOR_ENABLED_DEFAULT = getattr(const, "monitor_enabled", True)
# Normalizar ruta de status para no depender del cwd
_STATUS_PATH = Path(getattr(const, "status_file", "logs/status.json"))
if not _STATUS_PATH.is_absolute():
    _STATUS_PATH = Path(__file__).resolve().parent.parent / _STATUS_PATH
STATUS_FILE = _STATUS_PATH
MONITOR_HOST = getattr(const, "monitor_host", "0.0.0.0")
MONITOR_PORT = int(getattr(const, "monitor_port", 8088))
MONITOR_AUTH_USER = os.environ.get("MONITOR_AUTH_USER") or getattr(const, "monitor_auth_user", None)
MONITOR_AUTH_PASSWORD = os.environ.get("MONITOR_AUTH_PASSWORD") or getattr(const, "monitor_auth_password", None)
MONITOR_LOGO_PATH = os.environ.get("MONITOR_LOGO_PATH")
if not MONITOR_LOGO_PATH and const:
    MONITOR_LOGO_PATH = getattr(const, "monitor_logo_path", None)
MONITOR_LOGO_PATH = MONITOR_LOGO_PATH or "/home/dynatek/dynatek_.png"
LOGO_FILE = Path(MONITOR_LOGO_PATH)

MONITOR_TAGLINE = os.environ.get("MONITOR_TAGLINE")
if not MONITOR_TAGLINE and const:
    MONITOR_TAGLINE = getattr(const, "monitor_tagline", None)
MONITOR_TAGLINE = MONITOR_TAGLINE or "BMS | Aseguramos confort y control preciso"

MONITOR_UNIT_NAME = os.environ.get("MONITOR_UNIT_NAME")
if not MONITOR_UNIT_NAME and const:
    MONITOR_UNIT_NAME = getattr(const, "monitor_unit_name", None)
MONITOR_UNIT_NAME = MONITOR_UNIT_NAME or "Monitor manejadora"


def _sanitize_json(value: Any) -> Any:
    """Convierte valores no serializables a representaciones JSON seguras."""
    if isinstance(value, dict):
        return {str(k): _sanitize_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_json(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _registers_snapshot(shared_state) -> List[Dict[str, Any]]:
    try:
        shared_regs = list(shared_state.get("registers", []))
        if shared_regs:
            return shared_regs
    except Exception:
        pass
    if not regist:
        return []
    try:
        tipico_id = int(shared_state.get("tipico"))
    except Exception:
        tipico_id = 1
    regs = regist.get_registers_for_tipico(tipico_id)
    snap_map = regist.snapshot(tipico_id)
    rows = []
    for item in regs:
        name = item.get("name", "")
        val = snap_map.get(name) if name else item.get("value")
        rows.append(
            {
                "slave_id": item.get("slave_id"),
                "type": item.get("type"),
                "address": item.get("address"),
                "name": name,
                "value": _sanitize_json(val),
                "scale": item.get("scale", 1.0),
                "words": item.get("words", 1),
            }
        )
    return rows


def _tipico_required_keys(tipico_id: int) -> Dict[str, set]:
    if not tipicos:
        return {"required_sensors": set(), "required_actuators": set()}
    cfg = tipicos.get_tipico_config(tipico_id)
    return {
        "required_sensors": set(cfg.get("required_sensors", set())),
        "required_actuators": set(cfg.get("required_actuators", set())),
    }


def _runtime_snapshot(shared_state) -> dict:
    try:
        return runtime_config._snapshot_editable(shared_state)
    except Exception:
        return {}


def _horario_snapshot(load_file: bool = False) -> dict:
    try:
        return calendario.get_horario_config(load_file=load_file)
    except Exception as exc:
        return {"error": "horario_snapshot_error", "detail": str(exc)}


def snapshot_state(shared_state) -> dict:
    enabled = bool(shared_state.get("on_off_global", True))
    tipico_id = int(shared_state.get("tipico", getattr(tipicos, "DEFAULT_TIPICO", 1)))
    sensors = dict(shared_state.get("sensors", {}))
    outputs = dict(shared_state.get("actuators", {}))
    required = _tipico_required_keys(tipico_id)
    allowed = runtime_config.allowed_keys_for_tipico(tipico_id)
    sensors = {k: v for k, v in sensors.items() if k in allowed.get("allowed_sensors", set())}
    outputs = {k: v for k, v in outputs.items() if k in allowed.get("allowed_actuators", set())}
    settings_filtered = runtime_config._feature_filtered_settings(shared_state.get("settings", {}), tipico_id)
    settings_filtered = {k: v for k, v in settings_filtered.items() if k in allowed.get("allowed_settings", set())}
    setpoints_filtered = runtime_config._filter_setpoints(shared_state.get("setpoints", {}), tipico_id)

    return {
        "on_off_global": enabled,
        "mode": shared_state.get("mode", "AUTO"),
        "tipico": tipico_id,
        "setpoints": _sanitize_json(setpoints_filtered),
        "settings": _sanitize_json(settings_filtered),
        "sensors": _sanitize_json(sensors),
        "outputs": _sanitize_json(outputs),
        "alarms": _sanitize_json(dict(shared_state.get("alarms", {}))),
        "required_by_tipico": {
            "sensors": sorted(required["required_sensors"]),
            "actuators": sorted(required["required_actuators"]),
        },
        "registers": _sanitize_json(_registers_snapshot(shared_state)),
        "calendar": _sanitize_json(dict(shared_state.get("calendar", {}))),
        "ts": time.time(),
    }


def _build_monitor_html() -> str:
    html = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title> DYNATEK - Monitor Manejadora </title>
  <style>
    body { font-family: 'Poppins', 'Segoe UI', 'Helvetica Neue', sans-serif; margin: 0; padding: 16px; background: radial-gradient(circle at 20% 20%, #111827, #0b1220 45%, #0f172a); color: #e2e8f0; }
    .hero { display: flex; justify-content: space-between; align-items: center; background: linear-gradient(120deg, #0ea5e9, #22c55e); padding: 18px 20px; border-radius: 12px; box-shadow: 0 12px 28px rgba(0,0,0,0.35); margin-bottom: 12px; }
    .brand { display: flex; align-items: center; gap: 18px; color: #0b1220; }
    .logo { width: 110px; height: 110px; border-radius: 18px; background: #0b1220; display: grid; place-items: center; box-shadow: inset 0 0 0 1px rgba(255,255,255,0.08), 0 12px 22px rgba(0,0,0,0.35); }
    .title { font-weight: 700; font-size: 1.2rem; letter-spacing: 0.5px; }
    .subtitle { font-size: 0.9rem; opacity: 0.85; }
    .tagline { font-size: 0.95rem; color: #0b1220; font-weight: 600; }
    .meta-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 6px; }
    .meta-pill { background: rgba(148, 163, 184, 0.18); color: #e2e8f0; padding: 6px 10px; border-radius: 10px; border: 1px solid rgba(148, 163, 184, 0.28); font-weight: 600; }
    .meta-pill.ok { background: rgba(34, 197, 94, 0.2); border-color: rgba(34, 197, 94, 0.55); color: #bbf7d0; }
    .meta-pill.bad { background: rgba(239, 68, 68, 0.2); border-color: rgba(248, 113, 113, 0.55); color: #fecdd3; }
    .meta-req { font-size: 0.9rem; color: #cbd5e1; margin-bottom: 10px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; align-items: start; }
    .card { background: rgba(30, 41, 59, 0.9); border: 1px solid rgba(148, 163, 184, 0.12); border-radius: 10px; padding: 12px; box-shadow: 0 8px 18px rgba(0,0,0,0.28); backdrop-filter: blur(4px); }
    .card h3 { margin: 0 0 8px 0; }
    .meta { font-size: 0.92rem; color: #93c5fd; margin-bottom: 8px; font-weight: 600; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th, td { border-bottom: 1px solid #334155; padding: 6px; text-align: left; vertical-align: top; }
    th { color: #cbd5e1; background: rgba(51, 65, 85, 0.6); }
    tr:nth-child(even) td { background: rgba(15, 23, 42, 0.35); }
    tr:hover td { background: rgba(59, 130, 246, 0.12); }
    .ok { color: #86efac; }
    .bad { color: #fca5a5; }
    code { color: #7dd3fc; }
    textarea { width: 100%; min-height: 220px; background: #0b1220; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; padding: 8px; font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace; }
    button { background: #10b981; color: #0b172a; border: 0; border-radius: 6px; padding: 8px 12px; font-weight: 600; cursor: pointer; box-shadow: 0 6px 14px rgba(16,185,129,0.35); transition: transform 120ms ease, box-shadow 120ms ease; }
    button:hover { transform: translateY(-1px); box-shadow: 0 9px 20px rgba(16,185,129,0.35); }
    button.secondary { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; box-shadow: none; }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 6px; }
    .status-msg { font-size: 0.85rem; color: #93c5fd; }
  </style>
</head>
<body>
  <header class="hero">
    <div class="brand">
      <div class="logo">
        <img src="/logo.png" alt="Logo Dynatek" style="width:100%;height:100%;object-fit:contain;border-radius:13px;" />
      </div>
      <div>
        <div class="title">DYNATEK</div>
        <div class="subtitle">__UNIT_NAME__</div>
        <div class="tagline">__TAGLINE__</div>
      </div>
    </div>
  </header>
  <div class="meta" id="meta">Cargando...</div>
  <div class="grid">
    <div class="card">
      <h3>Sensores</h3>
      <table><tbody id="sensors"></tbody></table>
    </div>
    <div class="card">
      <h3>Actuadores</h3>
      <table><tbody id="outputs"></tbody></table>
    </div>
    <div class="card">
      <h3>Alarmas</h3>
      <table><tbody id="alarms"></tbody></table>
    </div>
    <div class="card">
      <h3>Setpoints / Settings</h3>
      <table><tbody id="config"></tbody></table>
    </div>
  </div>

  <div class="card" style="margin-top:12px;">
    <h3>Runtime config (edición JSON)</h3>
    <p class="meta">Edita los mismos campos que <code>var/runtime_config.json</code>. Al guardar se aplican en caliente y se persisten en el archivo.</p>
    <textarea id="runtimeText" spellcheck="false"></textarea>
    <div class="row">
      <button class="secondary" onclick="loadRuntime()">Refrescar</button>
      <button onclick="saveRuntime()">Guardar</button>
      <span id="runtimeStatus" class="status-msg"></span>
    </div>
  </div>

  <div class="card" style="margin-top:12px;">
    <h3>Forzar sensores (simulación)</h3>
    <p class="meta">Úsalo con <code>use_modbus_hw=False</code>. Inyecta valores de sensores en tiempo real.</p>
    <textarea id="forceText" spellcheck="false" placeholder='{"temperatura_suministro":23.5,"temperatura_retorno":29.1,"estatus_ventilador":1}'></textarea>
    <div class="row">
      <button class="secondary" onclick="loadForce()">Refrescar</button>
      <button onclick="saveForce()">Aplicar</button>
      <button class="secondary" onclick="clearForce()">Limpiar</button>
      <span id="forceStatus" class="status-msg"></span>
    </div>
  </div>

  <div class="card" style="margin-top:12px;">
    <h3>Registros Modbus (todas las periferias)</h3>
    <table>
      <thead>
        <tr><th>Slave</th><th>Tipo</th><th>Addr</th><th>Nombre</th><th>Valor</th><th>Words</th></tr>
      </thead>
      <tbody id="registers"></tbody>
    </table>
  </div>

  <script>
    function row(k, v) {
      const value = v === undefined || v === null ? '' : v;
      return `<tr><td><code>${k}</code></td><td>${String(value)}</td></tr>`;
    }

    function filterData(data, allowedKeys) {
      const allowed = (allowedKeys || []).filter(Boolean);
      return Object.fromEntries(
        Object.entries(data || {}).filter(([k]) => {
          const key = String(k || '').toLowerCase();
          if (key.startsWith('comp')) return false; // ocultar compresores
          if (!allowed.length) return true;
          return allowed.includes(k);
        })
      );
    }

    function withMonitorSensors(allowedKeys, data) {
      const visible = Array.isArray(allowedKeys) ? [...allowedKeys] : [];
      if ((data || {}).temperatura_suministro !== undefined && !visible.includes('temperatura_suministro')) {
        visible.unshift('temperatura_suministro');
      }
      return visible;
    }

    function renderMap(targetId, data) {
      const el = document.getElementById(targetId);
      const keys = Object.keys(data || {}).sort();
      el.innerHTML = keys.map((k) => row(k, data[k])).join('');
    }

    function renderRegisters(rows) {
      const el = document.getElementById('registers');
      el.innerHTML = (rows || []).map((r) => {
        const n = r.name || '<span style="opacity:.55">(sin asignar)</span>';
        const val = r.value === undefined || r.value === null ? '' : r.value;
        return `<tr><td>${r.slave_id}</td><td>${r.type}</td><td>${r.address}</td><td>${n}</td><td>${val}</td><td>${r.words}</td></tr>`;
      }).join('');
    }

    function renderMetaBar(data) {
      const ts = new Date((data.ts || 0) * 1000).toLocaleString();
      const reqSensors = data.required_by_tipico?.sensors || [];
      const reqActuators = data.required_by_tipico?.actuators || [];
      return `
        <div class="meta-bar">
          <span class="meta-pill">Típico: <b>${data.tipico}</b></span>
          <span class="meta-pill">Modo: <b>${data.mode}</b></span>
          <span class="meta-pill ${data.on_off_global ? 'ok' : 'bad'}">Global: <b>${data.on_off_global ? 'ON' : 'OFF'}</b></span>
          <span class="meta-pill">Actualizado: ${ts}</span>
        </div>
        <div class="meta-req">Requeridos → sensores: <code>${reqSensors.join(', ') || '-'}</code> | actuadores: <code>${reqActuators.join(', ') || '-'}</code></div>
      `;
    }

    async function loadRuntime() {
      const statusEl = document.getElementById('runtimeStatus');
      try {
        const res = await fetch('/api/runtime');
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        document.getElementById('runtimeText').value = JSON.stringify(data, null, 2);
        statusEl.textContent = 'Cargado';
      } catch (err) {
        statusEl.textContent = 'Error cargando runtime: ' + err.message;
      }
    }

    async function saveRuntime() {
      const statusEl = document.getElementById('runtimeStatus');
      try {
        const text = document.getElementById('runtimeText').value || '{}';
        const payload = JSON.parse(text);
        const res = await fetch('/api/runtime', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || res.statusText);
        document.getElementById('runtimeText').value = JSON.stringify(data.runtime, null, 2);
        statusEl.textContent = 'Guardado ' + new Date(data.ts * 1000).toLocaleTimeString();
      } catch (err) {
        statusEl.textContent = 'Error guardando: ' + err.message;
      }
    }

    async function loadForce() {
      const el = document.getElementById('forceStatus');
      try {
        const res = await fetch('/api/force');
        const data = await res.json();
        document.getElementById('forceText').value = JSON.stringify(data.forced || {}, null, 2);
        el.textContent = 'Cargado';
      } catch (err) {
        el.textContent = 'Error cargando: ' + err.message;
      }
    }

    async function saveForce() {
      const el = document.getElementById('forceStatus');
      try {
        const text = document.getElementById('forceText').value || '{}';
        const payload = JSON.parse(text);
        const res = await fetch('/api/force', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || res.statusText);
        document.getElementById('forceText').value = JSON.stringify(data.forced || {}, null, 2);
        el.textContent = 'Aplicado ' + new Date(data.ts * 1000).toLocaleTimeString();
      } catch (err) {
        el.textContent = 'Error aplicando: ' + err.message;
      }
    }

    async function clearForce() {
      const el = document.getElementById('forceStatus');
      try {
        const res = await fetch('/api/force/clear', { method: 'POST' });
        const data = await res.json();
        document.getElementById('forceText').value = JSON.stringify({}, null, 2);
        el.textContent = 'Limpio ' + new Date(data.ts * 1000).toLocaleTimeString();
      } catch (err) {
        el.textContent = 'Error limpiando: ' + err.message;
      }
    }

    async function refresh() {
      try {
        const response = await fetch('/api/status');
        const data = await response.json();
        document.getElementById('meta').innerHTML = renderMetaBar(data);

        const reqSensors = data.required_by_tipico?.sensors || [];
        const reqActuators = data.required_by_tipico?.actuators || [];

        const sensors = filterData(data.sensors, withMonitorSensors(reqSensors, data.sensors));
        const outputs = filterData(data.outputs, reqActuators);
        const alarms = filterData(data.alarms);

        renderMap('sensors', sensors);
        renderMap('outputs', outputs);
        renderMap('alarms', alarms);

        const cfg = Object.assign({}, data.setpoints || {}, data.settings || {});
        const cfgFiltered = filterData(cfg);
        renderMap('config', cfgFiltered);
        renderRegisters(data.registers || []);
      } catch (err) {
        document.getElementById('meta').textContent = 'Error consultando /api/status: ' + err;
      }
    }

    refresh();
    loadRuntime();
    setInterval(refresh, 1000);
  </script>
</body>
</html>
"""
    return html.replace("__TAGLINE__", MONITOR_TAGLINE).replace("__UNIT_NAME__", MONITOR_UNIT_NAME)


def _build_handler(shared_state):
    class MonitorHandler(BaseHTTPRequestHandler):
        def _safe_write(self, body: bytes, content_type: str, status: int = HTTPStatus.OK):
            """Envía respuesta y atrapa desconexiones del cliente (Broken pipe / reset)."""
            try:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            except (ConnectionResetError, BrokenPipeError):
                # El cliente cerró la conexión antes de tiempo; solo lo registramos silenciosamente.
                return

        def _json(self, payload: dict, status: int = HTTPStatus.OK):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._safe_write(body, "application/json; charset=utf-8", status=status)

        def _html(self, html: str, status: int = HTTPStatus.OK):
            body = html.encode("utf-8")
            self._safe_write(body, "text/html; charset=utf-8", status=status)

        def _auth_enabled(self) -> bool:
            return bool(MONITOR_AUTH_USER or MONITOR_AUTH_PASSWORD)

        def _unauthorized(self):
            body = b"Auth required"
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.send_header("WWW-Authenticate", 'Basic realm="manejadora", charset="UTF-8"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _check_auth(self) -> bool:
            if not self._auth_enabled():
                return True
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Basic "):
                self._unauthorized()
                return False
            try:
                decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
                user, pwd = decoded.split(":", 1)
            except Exception:
                self._unauthorized()
                return False
            if (MONITOR_AUTH_USER is not None and user != str(MONITOR_AUTH_USER)) or (
                MONITOR_AUTH_PASSWORD is not None and pwd != str(MONITOR_AUTH_PASSWORD)
            ):
                self._unauthorized()
                return False
            return True

        def do_GET(self):
            if not self._check_auth():
                return
            parsed = urlparse(self.path)
            if parsed.path == "/logo.png":
                if LOGO_FILE and LOGO_FILE.exists():
                    try:
                        data = LOGO_FILE.read_bytes()
                        self._safe_write(data, "image/png", status=HTTPStatus.OK)
                    except Exception:
                        self._json({"error": "logo_read_error"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                else:
                    self._json({"error": "logo_not_found"}, status=HTTPStatus.NOT_FOUND)
                return
            if parsed.path in ("/", "/index.html"):
                self._html(_build_monitor_html())
                return
            if parsed.path == "/api/status":
                payload = snapshot_state(shared_state)
                self._json(payload)
                return
            if parsed.path == "/api/runtime":
                self._json(_runtime_snapshot(shared_state))
                return
            if parsed.path == "/api/horario":
                self._json(_horario_snapshot(load_file=True))
                return
            if parsed.path == "/api/registers":
                query = parse_qs(parsed.query)
                selected_slave = query.get("slave_id", [None])[0]
                rows = payload = snapshot_state(shared_state).get("registers", [])
                if selected_slave is not None:
                    try:
                        sid = int(selected_slave)
                        rows = [r for r in rows if int(r.get("slave_id", -1)) == sid]
                    except Exception:
                        pass
                self._json({"registers": rows, "count": len(rows)})
                return
            if parsed.path == "/api/force":
                forced = dict((shared_state.get("forced_inputs") or {}))
                self._json({"forced": forced})
                return
            self._json({"error": "not_found", "path": parsed.path}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self):
            if not self._check_auth():
                return
            parsed = urlparse(self.path)
            if parsed.path == "/api/runtime":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except Exception:
                    length = 0
                if length > 8192:
                    self._json({"error": "payload_too_large"}, status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                    return
                raw = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    payload = json.loads(raw.decode("utf-8") or "{}")
                except Exception:
                    self._json({"error": "bad_json"}, status=HTTPStatus.BAD_REQUEST)
                    return
                if not isinstance(payload, dict):
                    self._json({"error": "payload_must_be_object"}, status=HTTPStatus.BAD_REQUEST)
                    return

                allowed_top = getattr(runtime_config, "_ALLOWED_TOP", {"tipico", "on_off_global", "mode", "setpoints", "settings"})
                sanitized = {k: v for k, v in payload.items() if k in allowed_top}
                if "setpoints" in sanitized and not isinstance(sanitized.get("setpoints"), dict):
                    sanitized.pop("setpoints", None)
                if "settings" in sanitized and not isinstance(sanitized.get("settings"), dict):
                    sanitized.pop("settings", None)

                runtime_config._apply(shared_state, sanitized)
                snapshot = _runtime_snapshot(shared_state)
                self._json({"ok": True, "runtime": snapshot, "ts": time.time()})
                return
            if parsed.path == "/api/horario":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except Exception:
                    length = 0
                if length > 16384:
                    self._json({"error": "payload_too_large"}, status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                    return
                raw = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    payload = json.loads(raw.decode("utf-8") or "{}")
                except Exception:
                    self._json({"error": "bad_json"}, status=HTTPStatus.BAD_REQUEST)
                    return
                if not isinstance(payload, dict):
                    self._json({"error": "payload_must_be_object"}, status=HTTPStatus.BAD_REQUEST)
                    return
                try:
                    snapshot = calendario.apply_horario_config(payload, persist=True)
                    calendario.apply_calendar_once(shared_state)
                except ValueError as exc:
                    self._json({"error": "invalid_horario", "detail": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                    return
                except Exception as exc:
                    self._json({"error": "horario_apply_error", "detail": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                    return
                self._json({"ok": True, "horario": snapshot, "calendar": dict(shared_state.get("calendar", {})), "ts": time.time()})
                return
            if parsed.path == "/api/force":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except Exception:
                    length = 0
                raw = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    payload = json.loads(raw.decode("utf-8") or "{}")
                except Exception:
                    self._json({"error": "bad_json"}, status=HTTPStatus.BAD_REQUEST)
                    return
                if not isinstance(payload, dict):
                    self._json({"error": "payload_must_be_object"}, status=HTTPStatus.BAD_REQUEST)
                    return
                forced = shared_state.get("forced_inputs")
                if forced is not None:
                    forced.clear()
                    for k, v in payload.items():
                        forced[k] = v
                self._json({"ok": True, "forced": dict(payload), "ts": time.time()})
                return
            if parsed.path == "/api/force/clear":
                forced = shared_state.get("forced_inputs")
                if forced is not None:
                    forced.clear()
                self._json({"ok": True, "forced": {}, "ts": time.time()})
                return

            self._json({"error": "not_found", "path": parsed.path}, status=HTTPStatus.NOT_FOUND)

        def log_message(self, format, *args):
            # reduce ruido
            return

    return MonitorHandler


def monitor_loop(shared_state, stop_event):
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except Exception:
        pass

    monitor_enabled = bool((shared_state.get("settings") or {}).get("monitor_enabled", MONITOR_ENABLED_DEFAULT))
    if not monitor_enabled:
        print("[monitor] Monitor deshabilitado en runtime_config.json.")
        while not stop_event.is_set():
            time.sleep(1)
        return

    print(f"[monitor] HTTP monitor activo en http://{MONITOR_HOST}:{MONITOR_PORT}")

    def _writer_loop():
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        while not stop_event.is_set():
            payload = snapshot_state(shared_state)
            tmp_path = STATUS_FILE.with_suffix(".json.tmp")
            try:
                with tmp_path.open("w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                tmp_path.replace(STATUS_FILE)
            except Exception as exc:  # pragma: no cover - runtime
                print(f"[monitor] No se pudo escribir {STATUS_FILE}: {exc}")
            time.sleep(1.0)

    writer_thread = threading.Thread(target=_writer_loop, daemon=True)
    writer_thread.start()

    server = ThreadingHTTPServer((MONITOR_HOST, MONITOR_PORT), _build_handler(shared_state))
    server.timeout = 0.5

    try:
        while not stop_event.is_set():
            server.handle_request()
    finally:
        try:
            server.server_close()
        except Exception:
            pass
