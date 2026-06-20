# Calendario operativo (`func/calendario.py`)

El módulo `func/calendario.py` calcula la solicitud horaria de la manejadora. Evalúa reglas semanales, excepciones por fecha y eventos prioritarios; luego publica solo el resultado en `shared_state["calendar"]`. `shared_state["on_off_global"]` queda reservado como comando global/manual de operador o configuración runtime.

## Flujo de ejecución

1. `main.py` crea `shared_state["calendar"]` con el último estado del calendario.
2. Antes de iniciar los procesos, `main.py` ejecuta una evaluación inicial con `apply_calendar_once()`.
3. El proceso `calendario_loop()` queda corriendo en paralelo y reevalúa el horario cada `ciclo_segundos`.
4. Si existe `var/horario.json`, el proceso lo recarga cuando cambia su `mtime`.
5. El calendario publica `enabled`, `request`, `q`, `source`, `detail` y metadatos en `shared_state["calendar"]`; no escribe `shared_state["on_off_global"]`.
6. `func/state.py` recalcula y publica `shared_state["on_off_effective"]`; el control solo lee esa salida efectiva.


## Habilitación efectiva

La política operativa queda centralizada en `func/state.py`:

1. `shared_state["on_off_global"]` conserva la solicitud global/manual del operador o de `runtime_config.json`.
2. `shared_state["calendar"]` conserva solo la señal propia del calendario (`q`/`request`) y nunca reemplaza `on_off_global`.
3. `shared_state["on_off_effective"]` se calcula como `on_off_global AND calendar_request`; si el calendario está deshabilitado, `calendar_request` se considera `ON` por seguridad operacional.

Los comandos MQTT `POWER`/`ON_OFF`/`ENCENDIDO` actualizan la solicitud global y publican el resultado efectivo. El comando `SCHEDULE_MODE`/`POWER_POLICY` mantiene la interfaz pública para volver a `AUTO` o fijar un modo explícito. `runtime_config.json` persiste/restaura `on_off_global` y `schedule_mode`.

## Prioridad de reglas

El cálculo de solicitud (`REQ`) usa esta prioridad:

1. `eventos_prioritarios`: override absoluto por rango de fecha/hora.
2. `excepciones_fecha`: reemplaza el horario semanal para una fecha específica.
3. `horario_semanal`: intervalos recurrentes de lunes a domingo.
4. `estado_fuera_de_horario`: estado por defecto si no hay intervalos activos.

Después de calcular `REQ`, se aplican temporizadores IEC 61131-3:

- `retardo_encendido_seg`: retardo tipo TON antes de activar `Q`.
- `retardo_apagado_seg`: retardo tipo TOF antes de desactivar `Q`.

## Archivo persistente

La API persiste cambios en:

```text
var/horario.json
```

La ruta se define en `var/const.py` mediante `horario_config_file`. Si el archivo no existe, el módulo usa los defaults definidos en `func/calendario.py`.

## Consultar el horario actual

```bash
curl -u dynatek:dynatek http://192.168.30.13:8088/api/horario
```

Respuesta resumida:

```json
{
  "calendario_habilitado": true,
  "zona_horaria": "America/Panama",
  "ciclo_segundos": 10.0,
  "retardo_encendido_seg": 0.0,
  "retardo_apagado_seg": 0.0,
  "estado_fuera_de_horario": false,
  "horario_semanal": {
    "LUN": [["00:00", "24:00"]],
    "MAR": [["00:00", "24:00"]],
    "MIE": [["00:00", "24:00"]],
    "JUE": [["00:00", "24:00"]],
    "VIE": [["00:00", "24:00"]],
    "SAB": [["00:00", "24:00"]],
    "DOM": [["00:00", "24:00"]]
  },
  "excepciones_fecha": {},
  "eventos_prioritarios": [],
  "archivo": "/home/dynatek/manejadora_app/var/horario.json"
}
```

## Modificar con `/api/horario`

Enviar `POST /api/horario` con JSON. La API valida el payload, lo aplica en caliente, escribe `var/horario.json` y actualiza `shared_state["calendar"]`.

```bash
curl -u dynatek:dynatek \
  -H 'Content-Type: application/json' \
  -X POST http://192.168.30.13:8088/api/horario \
  -d '{
    "calendario_habilitado": true,
    "zona_horaria": "America/Panama",
    "ciclo_segundos": 10,
    "retardo_encendido_seg": 0,
    "retardo_apagado_seg": 0,
    "estado_fuera_de_horario": false,
    "horario_semanal": {
      "LUN": [["00:00", "24:00"]],
      "MAR": [["00:00", "24:00"]],
      "MIE": [["00:00", "24:00"]],
      "JUE": [["00:00", "24:00"]],
      "VIE": [["00:00", "24:00"]],
      "SAB": [["00:00", "24:00"]],
      "DOM": [["00:00", "24:00"]]
    }
  }'
```

```bash
curl -u dynatek:dynatek \
  -H 'Content-Type: application/json' \
  -X POST http://192.168.30.13:8088/api/horario \
  -d '{
    "calendario_habilitado": true,
    "zona_horaria": "America/Panama",
    "ciclo_segundos": 10,
    "retardo_encendido_seg": 0,
    "retardo_apagado_seg": 0,
    "estado_fuera_de_horario": false,
    "horario_semanal": {
      "JUE": [["06:00", "14:00"]],
    }
  }'
```

### Campos aceptados

| Campo | Tipo | Descripción |
| --- | --- | --- |
| `calendario_habilitado` | boolean | Si es `false`, el calendario publica `enabled=false` y no limita la habilitación efectiva. |
| `zona_horaria` | string | Zona IANA, por ejemplo `America/Panama`. |
| `ciclo_segundos` | número | Periodo de evaluación. Mínimo efectivo: `0.25`. |
| `retardo_encendido_seg` | número | TON antes de encender. No acepta negativos. |
| `retardo_apagado_seg` | número | TOF antes de apagar. No acepta negativos. |
| `estado_fuera_de_horario` | boolean | Estado usado cuando no hay regla activa. |
| `horario_semanal` | objeto | Mapa de días `LUN`, `MAR`, `MIE`, `JUE`, `VIE`, `SAB`, `DOM` a listas de intervalos. |
| `excepciones_fecha` | objeto | Overrides por fecha `YYYY-MM-DD`. |
| `eventos_prioritarios` | lista | Overrides por rango de fecha/hora. |

También se aceptan alias en inglés: `enabled`, `timezone`, `cycle_seconds`, `on_delay_seconds`, `off_delay_seconds`, `default_outside_schedule`, `weekly`, `exceptions` y `priority_events`.

## Formato de intervalos

Un intervalo usa dos strings de hora:

```json
["06:00", "18:00"]
```

Reglas:

- `"00:00"` a `"24:00"` significa día completo.
- `"22:00"` a `"06:00"` cruza medianoche.
- Una lista vacía apaga todo el día si `estado_fuera_de_horario` es `false`.

## Excepciones por fecha

```json
{
  "excepciones_fecha": {
    "2026-01-01": false,
    "2026-12-24": [["08:00", "12:00"]],
    "2026-12-25": true
  }
}
```

- `false`: apagado todo el día.
- `true`: encendido todo el día.
- Lista de intervalos: horario especial para esa fecha.

## Eventos prioritarios

```json
{
  "eventos_prioritarios": [
    {
      "nombre": "mantenimiento",
      "desde": "2026-06-10 14:00",
      "hasta": "2026-06-10 16:00",
      "estado": false
    }
  ]
}
```

Los eventos tienen prioridad máxima y aceptan fecha/hora en formato `YYYY-MM-DD HH:MM` o `YYYY-MM-DDTHH:MM`.

## Estado en `/api/status`

`/api/status` expone la solicitud global, la señal calendario y la salida efectiva junto al bloque `calendar`:

```json
{
  "schedule_mode": "AUTO",
  "manual_request": true,
  "calendar_request": true,
  "effective_on_off": true,
  "calendar": {
    "enabled": true,
    "request": true,
    "q": true,
    "source": "SEMANAL",
    "detail": "LUN 06:00-18:00",
    "now_local": "2026-06-11T09:00:00-05:00",
    "timezone": "America/Panama",
    "cycle_seconds": 10.0,
    "on_delay_seconds": 0.0,
    "off_delay_seconds": 0.0,
    "ts": 1781187600.0
  }
}
```

## Modificación segura

- Preferir `/api/horario` para cambios operativos en caliente.
- Editar `func/calendario.py` solo para cambiar defaults de fábrica o lógica de evaluación.
- Validar cambios con `python3 -m py_compile main.py func/calendario.py func/monitor.py` antes de desplegar.
