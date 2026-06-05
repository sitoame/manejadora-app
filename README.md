# Manejadora App

Aplicación de control para una unidad manejadora HVAC ejecutada en Python 3.12. El servicio coordina lectura/escritura Modbus RTU, control automático, telemetría InfluxDB, comandos MQTT, configuración en caliente y un monitor HTTP local.

## Alcance funcional

- **Orquestación multiproceso**: `main.py` crea un estado compartido y levanta procesos independientes para runtime config, Modbus, control, ingesta, MQTT y monitor HTTP.
- **Control HVAC**: `func/control.py` calcula salidas automáticas para ventilador, VFD, válvula, compresores, solenoides, calentador, compuerta y UV según el típico activo.
- **Modbus RTU**: `func/modbus.py` lee sensores y escribe coils/registers hacia la periferia configurada.
- **MQTT**: `func/mqtt.py` recibe comandos operativos y publica estado periódico.
- **InfluxDB**: `func/ingesta.py` arma el payload de sensores, actuadores, setpoints y alarmas para persistencia histórica.
- **Monitor HTTP**: `func/monitor.py` expone vista web, estado JSON, edición de `runtime_config` y forzado de sensores para simulación.
- **Configuración por típicos**: `var/tipicos.py` define capacidades, sensores, actuadores y setpoints disponibles por tipo de manejadora.

## Requisitos

- Python 3.12.
- Acceso al puerto serie Modbus configurado en `var/const.py` cuando `use_modbus_hw = True`.
- Broker MQTT si `mqtt_enabled = true`.
- InfluxDB si `ingest_enabled = true`.
- Permisos de escritura sobre `logs/` y `var/runtime_config.json`.

## Instalación

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configuración base

La configuración estática vive en `var/const.py`:

| Área | Variables principales |
| --- | --- |
| InfluxDB | `url_influx`, `api_token_influx`, `org_influx`, `bucket`, `influx_measurement` |
| Modbus | `modbus_port`, `modbus_baudrate`, `use_modbus_hw`, `enable_modbus_write`, `modbus_timeout` |
| MQTT | `mqtt_broker`, `mqtt_port`, `mqtt_topic_cmd`, `mqtt_topic_status`, `mqtt_username`, `mqtt_password` |
| Monitor | `monitor_host`, `monitor_port`, `monitor_auth_user`, `monitor_auth_password` |
| Runtime | `runtime_config_file`, `runtime_config_poll_seconds`, `setpoints_file` |

> Nota operativa: evita versionar credenciales productivas. Sustituye tokens, usuarios y contraseñas por valores del entorno objetivo antes de desplegar.

## Configuración en caliente

`var/runtime_config.json` se carga al arranque y se vigila de forma continua. Permite ajustar, sin reiniciar el servicio:

- `tipico`.
- `on_off_global`.
- `mode` (`AUTO` o `MANUAL`).
- `setpoints`.
- `settings` de control, PID, timeouts, MQTT, ingesta y monitor.
- `manual_overrides` para salidas forzadas.

El monitor HTTP también permite leer y guardar esta configuración desde `/api/runtime`.

## Ejecución

```bash
python3.12 -u main.py
```

Al iniciar, el proceso principal precarga `var/runtime_config.json`, inicializa el estado compartido y arranca los loops de ejecución.

### Simulación sin hardware

Para pruebas locales sin puerto serie, configura:

```python
use_modbus_hw = False
enable_modbus_write = False
```

en `var/const.py`. Después puedes forzar sensores desde el monitor HTTP mediante `/api/force` o desde la interfaz web.

## Monitor HTTP

Por defecto el monitor se configura con `monitor_host` y `monitor_port` en `var/const.py`.

Endpoints principales:

- `GET /`: interfaz web.
- `GET /api/status`: estado de sensores, actuadores, alarmas y configuración.
- `GET /api/runtime`: snapshot editable de runtime config.
- `POST /api/runtime`: aplica configuración JSON permitida.
- `GET /api/registers`: snapshot de registros Modbus.
- `GET /api/force`: sensores forzados activos.
- `POST /api/force`: aplica sensores forzados para simulación.
- `POST /api/force/clear`: limpia sensores forzados.

## MQTT

El cliente se suscribe a `mqtt_topic_cmd` y publica estado en `mqtt_topic_status`.

Formato mínimo de comando:

```json
{
  "command": "SET_TEMP",
  "value": 21.5
}
```

Si se incluye `controller`, el comando solo se aplica cuando coincide con `controller_id`.

Comandos soportados destacados:

- Setpoints: `SET_TEMP`, `SETPOINT_TEMP`, `SET_HUM`, `SETPOINT_HUM`.
- Operación: `POWER`, `ON_OFF`, `SET_TIPICO`, `MODE`, `MODO`.
- Manual/auto: `MANUAL`, `MODO_MANUAL`, `AUTO_ALL`, `AUTO_GLOBAL`.
- Forzados: `FORCE_FAN_ON`, `FORCE_FAN_OFF`, `FORCE_FAN_VEL`, `FORCE_HEATER`, `FORCE_VALVE`, `FORCE_VFD_DO_ON`, `FORCE_VFD_AO`, `FORCE_CONTACTOR_ON`, `FORCE_DAMPER`, `FORCE_UV_ON` y sus variantes `AUTO_*`.
- Alarmas: `RESET_ALARMS`, `CLEAR_ALARMS`, `RESET_FAN`, `RESET_HEATER`, `RESET_VALVE`, `RESET_HUMO`.

## Estructura del repositorio

```text
.
├── main.py                  # Entrada principal y orquestación de procesos
├── func/
│   ├── control.py           # Lógica de control automático/manual
│   ├── ingesta.py           # Envío de datos a InfluxDB
│   ├── modbus.py            # Comunicación Modbus RTU
│   ├── monitor.py           # Monitor HTTP y API local
│   ├── mqtt.py              # Cliente MQTT y comandos
│   └── runtime_config.py    # Configuración editable en caliente
├── utilities/               # Utilidades de persistencia, formato e ingesta
├── var/
│   ├── const.py             # Configuración estática
│   ├── regist.py            # Mapa de registros Modbus
│   ├── runtime_config.json  # Configuración runtime persistida
│   └── tipicos.py           # Definición de típicos HVAC
├── requirements.txt         # Dependencias Python 3.12
└── scripts/                 # Scripts operativos
```

## Validación rápida

```bash
python3.12 -m compileall main.py func utilities var prueba_modbus.py regisssstttt.py
python3.12 -m pip install -r requirements.txt
```

## Operación segura

- Verifica `use_modbus_hw` y `enable_modbus_write` antes de conectar a hardware real.
- Prueba cambios de `runtime_config.json` con `on_off_global = false` cuando sea posible.
- Mantén respaldos de `var/runtime_config.json` y `logs/setpoints.json` si se cambian setpoints en operación.
- Revisa alarmas activas antes de usar comandos de reset.
