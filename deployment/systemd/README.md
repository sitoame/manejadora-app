# Deployment systemd de Manejadora App

Esta carpeta instala la aplicación Python de este repositorio como un único servicio `manejadora-app.service`. El monitor web ya forma parte de `main.py`, por eso no existe unidad npm/UI separada.

## Componentes

- `manejadora-app.service.in`: plantilla de la unidad systemd renderizada por `install.sh` con rutas absolutas del host.
- `manejadora-app.target`: target opcional para operar el stack como grupo.
- `manejadora-app.env.example`: variables de entorno para credenciales y branding del monitor HTTP.
- `scripts/force_on.sh`: fuerza un actuador por `/api/runtime`.
- `scripts/force_off.sh`: fuerza un actuador a `false` por `/api/runtime`.
- `scripts/release_override.sh`: libera el override manual de un actuador y deja el modo en `AUTO` por defecto.

## Prerrequisitos

```bash
cd /ruta/manejadora-app
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

El servicio necesita permisos de lectura/escritura sobre `logs/`, `var/` y acceso al puerto Modbus configurado en `var/const.py` cuando `use_modbus_hw = True`.

## Instalación

```bash
cd /ruta/manejadora-app/deployment/systemd
sudo ./install.sh
```

Variables soportadas por el instalador:

- `APP_ROOT`: raíz del repositorio. Default: se detecta desde esta carpeta.
- `PYTHON_BIN`: intérprete Python. Default: `$APP_ROOT/.venv/bin/python3.12`.
- `SERVICE_USER`: usuario de ejecución. Default: usuario que invocó `sudo`.
- `SERVICE_GROUP`: grupo de ejecución. Default: grupo primario de `SERVICE_USER`.
- `SYSTEMD_DIR`: destino de unidades. Default: `/etc/systemd/system`.
- `ENV_DIR`: destino del env file. Default: `/etc/manejadora-app`.

Ejemplo explícito:

```bash
sudo APP_ROOT=/opt/manejadora-app \
  PYTHON_BIN=/opt/manejadora-app/.venv/bin/python3.12 \
  SERVICE_USER=dynatek \
  ./install.sh
```

## Configuración runtime del servicio

El instalador crea `/etc/manejadora-app/manejadora-app.env` desde `manejadora-app.env.example` si no existe. Edita ese archivo para cambiar credenciales o branding del monitor:

```bash
sudo nano /etc/manejadora-app/manejadora-app.env
sudo systemctl restart manejadora-app.service
```

La configuración operativa del controlador sigue viviendo en `var/const.py` y `var/runtime_config.json`.

## Operación diaria

```bash
sudo systemctl start manejadora-app.service
sudo systemctl stop manejadora-app.service
sudo systemctl restart manejadora-app.service
sudo systemctl status manejadora-app.service
sudo systemctl start manejadora-app.target
sudo systemctl stop manejadora-app.target
```

Logs:

```bash
journalctl -u manejadora-app.service -f
```

Verificación de unidad instalada:

```bash
sudo systemd-analyze verify /etc/systemd/system/manejadora-app.service
```

## Monitor HTTP

El monitor queda disponible en el host/puerto configurados por `var/const.py` (`0.0.0.0:8088` por defecto). Endpoints útiles:

- `GET /`: interfaz web integrada.
- `GET /api/status`: estado del controlador.
- `GET /api/runtime`: configuración editable en caliente.
- `POST /api/runtime`: aplica configuración permitida.
- `GET /api/force`: sensores forzados activos para simulación.
- `POST /api/force`: reemplaza sensores forzados.
- `POST /api/force/clear`: limpia sensores forzados.

## Overrides manuales desde scripts

Los scripts usan Basic Auth contra el monitor. Defaults:

- `API_BASE=http://127.0.0.1:8088`
- `MONITOR_AUTH_USER=dynatek`
- `MONITOR_AUTH_PASSWORD=dynatek`

Ejemplos:

```bash
API_BASE="http://127.0.0.1:8088" ./scripts/force_on.sh fan
API_BASE="http://127.0.0.1:8088" ./scripts/force_on.sh control_valvula 7.5
API_BASE="http://127.0.0.1:8088" ./scripts/force_off.sh fan
API_BASE="http://127.0.0.1:8088" ./scripts/release_override.sh fan
```

Para sensores de simulación, usa directamente `/api/force`:

```bash
curl -u dynatek:dynatek -X POST http://127.0.0.1:8088/api/force \
  -H 'Content-Type: application/json' \
  -d '{"temperatura_suministro":23.5,"estatus_ventilador":1}'
```

## Desinstalación

```bash
cd /ruta/manejadora-app/deployment/systemd
sudo ./uninstall.sh
```

Para borrar también `/etc/manejadora-app`:

```bash
sudo REMOVE_ENV=true ./uninstall.sh
```
