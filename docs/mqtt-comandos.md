w# Documentación de comandos MQTT

Este documento describe todos los comandos MQTT aceptados por `func/mqtt.py`, el formato del mensaje, el tópico de entrada, el tópico de estado y el efecto operativo sobre el estado compartido del controlador.

## Configuración MQTT

| Parámetro | Origen | Valor por defecto/fallback | Descripción |
| --- | --- | --- | --- |
| Broker | `var.const.mqtt_broker` | `181.78.120.121` | Host/IP del broker MQTT. |
| Puerto | `var.const.mqtt_port` | `1883` | Puerto TCP del broker. |
| Tópico de comandos | `var.const.mqtt_topic_cmd` | `manejadora_david` | Tópico al que se suscribe el cliente para recibir comandos. |
| Tópico de estado | `var.const.mqtt_topic_status` | `manejadora_david_status` | Tópico donde el cliente publica estado periódico. |
| Controller ID | `var.const.controller_id` | `eg628_david` | Identificador usado para filtrar comandos por controlador. |
| Usuario/password | `var.const.mqtt_username` / `var.const.mqtt_password` | `None` | Credenciales opcionales del broker. |
| Intervalo de estado | `var.const.mqtt_status_interval` | `30` s | Cadencia de publicación del estado. |
| Reintento de conexión | `var.const.mqtt_reconnect_seconds` | `5` s | Delay fijo entre reconexiones. |

En la configuración actual del repositorio, `var/const.py` define `mqtt_topic_cmd = 'manejadora_1'`, `mqtt_topic_status = 'manejadora_1_status'` y `controller_id = 'eg628_AM'`.

## Formato de entrada

Cada mensaje debe ser JSON y debe decodificar a un objeto.

```json
{
  "command": "SET_TEMP",
  "value": 21.5,
  "controller": "eg628_AM"
}
```

Campos:

| Campo | Tipo | Requerido | Descripción |
| --- | --- | --- | --- |
| `command` | string | Sí | Comando MQTT. Se normaliza a mayúsculas antes de procesarse. |
| `value` | any | Depende del comando | Valor principal del comando. |
| `controller` | string | No | Si se envía, el comando solo se ejecuta cuando coincide con `controller_id` sin distinguir mayúsculas/minúsculas. |
| `overrides` | object | Solo `MANUAL`/`MODO_MANUAL` | Mapa de salidas manuales a forzar. |
| `alarms` | object | Solo `SET_ALARMS` | Mapa de alarmas a activar/desactivar. |

Reglas generales:

- Un `controller` distinto al `controller_id` local hace que el comando se ignore.
- Un payload que no sea JSON válido o que no sea objeto se rechaza.
- Un comando no reconocido se registra como no aceptado y no modifica el estado.
- Los comandos de forzado escriben en `manual_overrides` y activan el flag `*_forced` del punto correspondiente.
- `POWER`/`ON_OFF` actualizan `on_off_global` como solicitud global/manual y recalculan `on_off_effective`; `SCHEDULE_MODE`/`POWER_POLICY` acepta `AUTO`, `MANUAL_ON` o `MANUAL_OFF`.

## Publicación de estado

El cliente publica periódicamente en el tópico de estado un JSON con esta estructura:

```json
{
  "controller": "eg628_AM",
  "on_off_global": true,
  "schedule_mode": "AUTO",
  "manual_request": true,
  "calendar_request": true,
  "effective_on_off": true,
  "on_off_effective": true,
  "mode": "AUTO",
  "setpoints": {},
  "outputs": {},
  "sensors": {}
}
```

Campos publicados:

| Campo | Descripción |
| --- | --- |
| `controller` | Identificador local del controlador. |
| `on_off_global` | Solicitud global/manual del operador. |
| `manual_request` | Misma solicitud global/manual normalizada para telemetría. |
| `calendar_request` | Señal propia del calendario; no reemplaza la solicitud global. |
| `effective_on_off` / `on_off_effective` | Estado aplicado calculado por `func/state.py` como solicitud global y calendario. |
| `mode` | Modo operativo actual (`AUTO`, `MANUAL` u otro valor recibido por `MODE`). |
| `setpoints` | Setpoints activos. |
| `outputs` | Salidas/actuadores actuales. |
| `sensors` | Lecturas de sensores actuales. |

## Catálogo completo de comandos

### Setpoints

| Comando(s) | `value` esperado | Efecto |
| --- | --- | --- |
| `SET_TEMP`, `SETPOINT_TEMP`, `SETPOINT_TEMPERATURA` | Número | Convierte `value` a `float`, actualiza `setpoints.temperature` y persiste los setpoints en `logs/setpoints.json` o en el archivo configurado por `setpoints_file`. |
| `SET_HUM`, `SETPOINT_HUM`, `SETPOINT_HUMEDAD` | Número | Convierte `value` a `float`, actualiza `setpoints.humidity` y persiste los setpoints. |

Ejemplos:

```json
{"command":"SET_TEMP","value":21.5}
```

```json
{"command":"SET_HUM","value":55}
```

### Operación global y configuración activa

| Comando(s) | `value` esperado | Efecto |
| --- | --- | --- |
| `POWER`, `ON_OFF`, `ENCENDIDO` | Booleano o valor convertible a `bool` | Actualiza `on_off_global` y recalcula `on_off_effective`. |
| `SET_TIPICO`, `TIPICO` | Entero | Convierte `value` a `int` y actualiza `tipico`. Si no se puede convertir, no cambia el típico y registra el error. |
| `SET_VFD_SPEED`, `VFD_SPEED` | Número 0-100 | Convierte `value` a `float`, limita el valor a `0.0..100.0` y actualiza `settings.vfd_speed_command_pct`. |
| `MODE`, `MODO` | String | Actualiza `mode` con `value.upper()`. Si el valor es `AUTO`, limpia todos los flags `*_forced`; si es otro valor, solo cambia el modo. |

Ejemplos:

```json
{"command":"POWER","value":true}
```

```json
{"command":"MODE","value":"AUTO"}
```

```json
{"command":"SET_TIPICO","value":2}
```

### Modo manual y overrides masivos

| Comando(s) | Payload esperado | Efecto |
| --- | --- | --- |
| `MANUAL`, `MODO_MANUAL` | `overrides` o `value` como objeto | Activa `mode = "MANUAL"`, copia cada salida indicada a `manual_overrides` y marca su `*_forced = True`. |

Salidas aceptadas dentro de `overrides`:

| Clave | Rango/tipo aplicado | Descripción |
| --- | --- | --- |
| `fan` | Booleano | Salida directa de ventilador. |
| `heater` | Número limitado a `0.0..100.0` | Comando porcentual del calentador. |
| `comando_contactor` | Booleano | Salida digital de contactor. |
| `comando_vfd` | Booleano | Salida digital de habilitación/comando VFD. |
| `control_frec_vfd` | Número limitado a `0.0..100.0` | Comando porcentual de frecuencia/velocidad VFD. |
| `control_valvula` | Número limitado a `0.0..10.0` | Salida analógica de válvula en V. |
| `control_compuerta_aire_exterior` | Número limitado a `0.0..10.0` | Salida analógica de compuerta de aire exterior en V. |
| `comando_luz_ultravioleta` | Booleano | Salida digital de luz UV. |

Si no se envían `overrides` ni `value`, el comando toma como punto de partida las salidas actuales de `actuators` y las deja forzadas.

Ejemplo:

```json
{
  "command": "MANUAL",
  "overrides": {
    "comando_vfd": true,
    "control_frec_vfd": 60,
    "control_valvula": 7.5,
    "heater": 0
  }
}
```

### Ventilador / VFD seleccionado por típico

Estos comandos usan `_fan_command_key()` para decidir qué salida digital forzar:

- Si el típico activo tiene `features.usa_vfd = true`, se fuerza `comando_vfd`.
- Si no usa VFD pero tiene `features.usa_contactor = true`, se fuerza `comando_contactor`.
- Si no aplica ninguno, se fuerza la salida directa `fan`.

| Comando(s) | `value` esperado | Efecto |
| --- | --- | --- |
| `FORCE_FAN_ON`, `FAN_ON` | No usado | Fuerza la salida digital seleccionada a `True` y marca su `*_forced = True`. |
| `FORCE_FAN_OFF`, `FAN_OFF` | No usado | Fuerza la salida digital seleccionada a `False` y marca su `*_forced = True`. |
| `AUTO_FAN`, `RESET_FORCE_FAN` | No usado | Limpia el flag forzado de la salida digital seleccionada y también de `fan`. |
| `FORCE_FAN_VEL`, `FORCE_FAN_SPEED`, `FAN_VEL`, `FAN_SPEED` | Número 0-100 | Fuerza `control_frec_vfd` al porcentaje indicado, limitado a `0.0..100.0`. |
| `AUTO_FAN_VEL`, `AUTO_FAN_SPEED`, `RESET_FORCE_FAN_VEL` | No usado | Limpia el flag forzado de `control_frec_vfd`. |

Ejemplos:

```json
{"command":"FAN_ON"}
```

```json
{"command":"FAN_SPEED","value":75}
```

### Calentador

| Comando(s) | `value` esperado | Efecto |
| --- | --- | --- |
| `FORCE_HEATER` | Número 0-100 | Fuerza `manual_overrides.heater` al porcentaje indicado, limitado a `0.0..100.0`, y marca `heater_forced = True`. |
| `AUTO_HEATER` | No usado | Limpia `heater_forced`. |

Ejemplo:

```json
{"command":"FORCE_HEATER","value":35}
```

### Válvula

| Comando(s) | `value` esperado | Efecto |
| --- | --- | --- |
| `FORCE_VALVE`, `VALVE_SET` | Número 0-10 | Fuerza `control_valvula` al voltaje indicado, limitado a `0.0..10.0`, y marca `control_valvula_forced = True`. |
| `AUTO_VALVE` | No usado | Limpia `control_valvula_forced`. |

Ejemplo:

```json
{"command":"VALVE_SET","value":6.25}
```

### VFD digital y analógico

| Comando(s) | `value` esperado | Efecto |
| --- | --- | --- |
| `FORCE_VFD_DO_ON`, `VFD_DO_ON` | No usado | Fuerza `comando_vfd = True` y marca `comando_vfd_forced = True`. |
| `FORCE_VFD_DO_OFF`, `VFD_DO_OFF` | No usado | Fuerza `comando_vfd = False` y marca `comando_vfd_forced = True`. |
| `AUTO_VFD_DO` | No usado | Limpia `comando_vfd_forced`. |
| `FORCE_VFD_AO`, `FORCE_VFD_FREQ` | Número 0-100 | Fuerza `control_frec_vfd` al porcentaje indicado, limitado a `0.0..100.0`, y marca `control_frec_vfd_forced = True`. |
| `AUTO_VFD_AO` | No usado | Limpia `control_frec_vfd_forced`. |

Ejemplos:

```json
{"command":"VFD_DO_ON"}
```

```json
{"command":"FORCE_VFD_FREQ","value":82}
```

### Contactor

| Comando(s) | `value` esperado | Efecto |
| --- | --- | --- |
| `FORCE_CONTACTOR_ON`, `CONTACTOR_ON` | No usado | Fuerza `comando_contactor = True` y marca `comando_contactor_forced = True`. |
| `FORCE_CONTACTOR_OFF`, `CONTACTOR_OFF` | No usado | Fuerza `comando_contactor = False` y marca `comando_contactor_forced = True`. |
| `AUTO_CONTACTOR` | No usado | Limpia `comando_contactor_forced`. |

Ejemplo:

```json
{"command":"CONTACTOR_ON"}
```

### Compuerta de aire exterior

| Comando(s) | `value` esperado | Efecto |
| --- | --- | --- |
| `FORCE_DAMPER` | Número 0-10 | Fuerza `control_compuerta_aire_exterior` al voltaje indicado, limitado a `0.0..10.0`, y marca `control_compuerta_aire_exterior_forced = True`. |
| `AUTO_DAMPER` | No usado | Limpia `control_compuerta_aire_exterior_forced`. |

Ejemplo:

```json
{"command":"FORCE_DAMPER","value":10}
```

### Luz ultravioleta

| Comando(s) | `value` esperado | Efecto |
| --- | --- | --- |
| `FORCE_UV_ON`, `UV_ON` | No usado | Fuerza `comando_luz_ultravioleta = True` y marca `comando_luz_ultravioleta_forced = True`. |
| `FORCE_UV_OFF`, `UV_OFF` | No usado | Fuerza `comando_luz_ultravioleta = False` y marca `comando_luz_ultravioleta_forced = True`. |
| `AUTO_UV` | No usado | Limpia `comando_luz_ultravioleta_forced`. |

Ejemplo:

```json
{"command":"UV_ON"}
```

### Retorno a automático / limpieza de forzados

| Comando(s) | `value` esperado | Efecto |
| --- | --- | --- |
| `AUTO_ALL`, `AUTO_GLOBAL` | No usado | Limpia todos los flags `*_forced` y cambia `mode` a `AUTO`. |
| `RESET_FORCE_ALL`, `AUTO_FORCE_ALL` | No usado | Limpia todos los flags `*_forced` sin cambiar `mode`. |

Los flags limpiados por estos comandos son:

- `fan_forced`
- `heater_forced`
- `comando_contactor_forced`
- `comando_vfd_forced`
- `control_frec_vfd_forced`
- `control_valvula_forced`
- `control_compuerta_aire_exterior_forced`
- `comando_luz_ultravioleta_forced`

Ejemplo:

```json
{"command":"AUTO_GLOBAL"}
```

### Alarmas y resets

| Comando(s) | `value` esperado | Efecto |
| --- | --- | --- |
| `RESET_ALARMS`, `CLEAR_ALARMS`, `RESET_ALARMAS` | No usado | Pone todas las alarmas en `False` y reinicia todos los timestamps de activación a `0.0`. |
| `RESET_CMD_FAN` | No usado | Genera un pulso de 2 s en `resets.fan`. |
| `RESET_CMD_HEATER` | No usado | Genera un pulso de 2 s en `resets.heater`. |
| `RESET_CMD_ALL` | No usado | Genera un pulso de 2 s en `resets.all`. |
| `RESET_FAN` | No usado | Limpia alarmas de ventilador/VFD y timestamps asociados; también pulsa `resets.fan`. |
| `RESET_HEATER` | No usado | Limpia alarma y timestamp de calentador; también pulsa `resets.heater`. |
| `RESET_VALVE`, `RESET_VALVULA` | No usado | Limpia alarmas de tracking de válvula y timestamps asociados; también pulsa `resets.valvula`. |
| `RESET_HUMO`, `RESET_SMOKE` | No usado | Limpia `interlock_humo` y pulsa `resets.humo`, salvo que `sensors.detector_humo` siga activo. |
| `SET_ALARMS` | `alarms` como objeto | Para cada clave incluida en `payload.alarms`, si existe en `shared_state.alarms`, la actualiza a `bool(value)`. |

Grupos de alarmas limpiados por reset específico:

| Grupo | Alarmas | Timestamps |
| --- | --- | --- |
| `fan` | `fan`, `alerta_ventilador`, `interlock_vfd`, `alerta_tracking_vfd`, `alerta_tracking_vfd_valvula` | `fan`, `ventilador`, `tracking_vfd`, `tracking_vfd_valvula` |
| `valvula` | `alerta_tracking_valvula`, `alerta_tracking_vfd_valvula` | `tracking_valvula`, `tracking_vfd_valvula` |
| `heater` | `heater` | `heater` |
| `humo` | `interlock_humo` | Ninguno |

Ejemplos:

```json
{"command":"RESET_ALARMS"}
```

```json
{
  "command": "SET_ALARMS",
  "alarms": {
    "alerta_ventilador": true,
    "alerta_uv": false
  }
}
```

## Lista alfabética de comandos y alias

- `AUTO_ALL`
- `AUTO_CONTACTOR`
- `AUTO_DAMPER`
- `AUTO_FAN`
- `AUTO_FAN_SPEED`
- `AUTO_FAN_VEL`
- `AUTO_FORCE_ALL`
- `AUTO_GLOBAL`
- `AUTO_HEATER`
- `AUTO_UV`
- `AUTO_VALVE`
- `AUTO_VFD_AO`
- `AUTO_VFD_DO`
- `CLEAR_ALARMS`
- `CONTACTOR_OFF`
- `CONTACTOR_ON`
- `ENCENDIDO`
- `FAN_OFF`
- `FAN_ON`
- `FAN_SPEED`
- `FAN_VEL`
- `FORCE_CONTACTOR_OFF`
- `FORCE_CONTACTOR_ON`
- `FORCE_DAMPER`
- `FORCE_FAN_OFF`
- `FORCE_FAN_ON`
- `FORCE_FAN_SPEED`
- `FORCE_FAN_VEL`
- `FORCE_HEATER`
- `FORCE_UV_OFF`
- `FORCE_UV_ON`
- `FORCE_VALVE`
- `FORCE_VFD_AO`
- `FORCE_VFD_DO_OFF`
- `FORCE_VFD_DO_ON`
- `FORCE_VFD_FREQ`
- `MANUAL`
- `MODE`
- `MODO`
- `MODO_MANUAL`
- `ON_OFF`
- `POWER`
- `RESET_ALARMAS`
- `RESET_ALARMS`
- `RESET_CMD_ALL`
- `RESET_CMD_FAN`
- `RESET_CMD_HEATER`
- `RESET_FAN`
- `RESET_FORCE_ALL`
- `RESET_FORCE_FAN`
- `RESET_FORCE_FAN_VEL`
- `RESET_HEATER`
- `RESET_HUMO`
- `RESET_SMOKE`
- `RESET_VALVE`
- `RESET_VALVULA`
- `SET_ALARMS`
- `SET_HUM`
- `SET_TEMP`
- `SET_TIPICO`
- `SET_VFD_SPEED`
- `SETPOINT_HUM`
- `SETPOINT_HUMEDAD`
- `SETPOINT_TEMP`
- `SETPOINT_TEMPERATURA`
- `TIPICO`
- `UV_OFF`
- `UV_ON`
- `VALVE_SET`
- `VFD_DO_OFF`
- `VFD_DO_ON`
- `VFD_SPEED`

## Ejemplos con `mosquitto_pub`

Publicar un setpoint de temperatura:

```bash
mosquitto_pub -h 192.168.30.11 -p 1883 -u telegraf -P telegraf -t manejadora_1 -m '{"controller":"eg628_AM","command":"SET_TEMP","value":21.5}'
```

Forzar VFD al 70 %:

```bash
mosquitto_pub -h 192.168.30.11 -p 1883 -u telegraf -P telegraf -t manejadora_1 -m '{"controller":"eg628_AM","command":"FORCE_VFD_FREQ","value":70}'
```

Volver todo a automático:

```bash
mosquitto_pub -h 192.168.30.11 -p 1883 -u telegraf -P telegraf -t manejadora_1 -m '{"controller":"eg628_AM","command":"AUTO_GLOBAL"}'
```
