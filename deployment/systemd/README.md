# Systemd deployment (Sprint 7.5)

## Componentes

- `plc-engine.service`: runtime HVAC Python (crítico).
- `plc-ui.service`: UI commissioning React/Vite/npm (auxiliar).
- `plc-app.target`: target agrupador opcional.

## Instalación

```bash
cd /home/maxia/plc_app/deployment/systemd
sudo ./install.sh
```

## Actualización de unidades

```bash
cd /home/maxia/plc_app/deployment/systemd
sudo systemctl stop plc-app.target
sudo cp plc-*.service plc-app.target /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start plc-app.target
```

## Operación diaria

```bash
sudo systemctl start plc-app.target
sudo systemctl stop plc-app.target
sudo systemctl restart plc-engine.service
sudo systemctl restart plc-ui.service
sudo systemctl status plc-engine.service
sudo systemctl status plc-ui.service
```

## Logs (journald)

```bash
journalctl -u plc-engine.service -f
journalctl -u plc-ui.service -f
```

## Configuración

- Engine env: `/home/maxia/plc_app/deployment/systemd/plc-engine.env`
- UI env: `/home/maxia/plc_app/deployment/systemd/plc-ui.env`

Copiar desde ejemplos si no existen:

```bash
cp plc-engine.env.example /home/maxia/plc_app/deployment/systemd/plc-engine.env
cp plc-ui.env.example /home/maxia/plc_app/deployment/systemd/plc-ui.env
```

Parámetros soportados:

- `ENGINE_PYTHON`
- `ENGINE_ENTRYPOINT`
- `PLC_CONFIG_PATH`
- `UI_HOST`
- `UI_PORT`

## Troubleshooting básico

- Ver sintaxis de unidades:

```bash
systemd-analyze verify /etc/systemd/system/plc-engine.service
systemd-analyze verify /etc/systemd/system/plc-ui.service
```

- Si falla UI por dependencias:

```bash
cd /home/maxia/plc_app/frontend
npm ci
sudo systemctl restart plc-ui.service
```

- Si falla engine por venv:

```bash
cd /home/maxia/plc_app
python3.10 -m venv .venv
.venv/bin/pip install -r requirements.txt
sudo systemctl restart plc-engine.service
```

## Desinstalación

```bash
cd /home/maxia/plc_app/deployment/systemd
sudo ./uninstall.sh
```

## Scheduler de encendido/apagado forzado

Scripts disponibles:

- `deployment/systemd/scripts/force_on.sh <output_name>`
- `deployment/systemd/scripts/force_off.sh <output_name>`
- `deployment/systemd/scripts/release_override.sh <output_name>`

Variables de entorno:

- `API_BASE` (default `http://192.168.1.121:8090`)
- `SOURCE` (default `COMMISSIONING`)

Si el engine está publicado en otra IP del segmento actual, exportar `API_BASE` con esa IP:

```bash
export API_BASE="http://192.168.1.121:8090"
```

Ejemplo de cron (UTC):

```cron
4 2 * * * API_BASE="http://192.168.1.121:8080" /home/maxia/plc_app/deployment/systemd/scripts/force_on.sh CHWP2_START >> /var/log/hvac_force.log 2>&1
0 22 * * * API_BASE="http://192.168.1.121:8090" /home/maxia/plc_app/deployment/systemd/scripts/force_off.sh ahu_supply_fan_cmd >> /var/log/hvac_force.log 2>&1
```

Si fuera de horario debe volver a AUTO en lugar de `false` fijo, usar `release_override.sh` en la segunda tarea.
