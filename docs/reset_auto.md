# Reset automático de alarmas críticas

`func/reset_auto.py` ejecuta un supervisor independiente que observa alarmas de paro total y genera un pulso en `shared_state["resets"]["all"]` cuando una alarma continúa activa después de una ventana definida.

## Objetivo

El proceso evita intervención manual repetitiva ante alarmas críticas persistentes. La secuencia no reemplaza el enclavamiento físico ni la condición real de seguridad: solo limpia banderas internas, reinicia temporizadores de software y ordena el pulso global de reset para que los módulos de salida puedan reintentar operación si la causa desapareció.

## Secuencia de operación

1. El loop lee `shared_state["settings"]` y valida si `reset_auto_enabled` está activo.
2. Obtiene `shared_state["alarms"]` y filtra las alarmas configuradas en `reset_auto_total_shutdown_alarms`.
3. Al detectar la primera alarma crítica activa, registra `first_alarm_ts` y conserva la misma secuencia mientras la alarma siga presente.
4. Dispara los resets acumulativos con esta agenda:
   - primer intento: 5 minutos desde la primera alarma;
   - segundo intento: 30 minutos desde la primera alarma;
   - tercer intento: 60 minutos desde la primera alarma;
   - siguientes intentos: cada 2 horas después del tercer intento.
5. En cada intento limpia `shared_state["alarms"]`, reinicia `shared_state["activation_ts"]` y activa `shared_state["resets"]["all"]` durante `reset_auto_pulse_seconds`.
6. Publica estado operativo en `shared_state["reset_auto"]` para monitorización HTTP/MQTT.
7. Si las alarmas desaparecen, conserva la secuencia durante `reset_auto_clear_grace_seconds`; esto evita volver al primer intento cuando la alarma se regenera justo después de un reset.

## Parámetros runtime

Los parámetros son editables desde `var/runtime_config.json` y desde las APIs que aplican `settings`:

| Setting | Tipo | Descripción |
| --- | --- | --- |
| `reset_auto_enabled` | bool | Habilita o deshabilita el supervisor. |
| `reset_auto_poll_seconds` | float | Periodo mínimo de evaluación del loop. Se limita internamente a 0.25 s como mínimo. |
| `reset_auto_pulse_seconds` | float | Duración del pulso `resets.all`. Se limita internamente a 0.1 s como mínimo. |
| `reset_auto_clear_grace_seconds` | float | Tiempo de gracia antes de cerrar una secuencia sin alarmas activas. |
| `reset_auto_total_shutdown_alarms` | list/string | Alarmas que activan la secuencia. Acepta lista JSON o texto separado por comas. |

## Estado publicado

`shared_state["reset_auto"]` expone:

| Campo | Descripción |
| --- | --- |
| `enabled` | Estado efectivo de habilitación. |
| `active` | Indica si existe una secuencia abierta. |
| `active_alarm_keys` | Alarmas críticas activas en el último ciclo. |
| `first_alarm_ts` | Timestamp de inicio de secuencia. |
| `last_active_ts` | Último timestamp con alarmas críticas activas. |
| `last_reset_ts` | Timestamp del último reset automático. |
| `resets_done` | Cantidad de resets ejecutados dentro de la secuencia actual. |
| `next_reset_ts` | Timestamp previsto para el siguiente reset. |
| `seconds_to_next_reset` | Segundos restantes para el siguiente reset. |
| `pulse_active` | Indica si el pulso `resets.all` sigue activo. |
| `ts` | Timestamp de publicación del estado. |

## Integración de procesos

`main.py` inicializa `shared_state["reset_auto"]`, carga los defaults en `shared_state["settings"]` y arranca `reset_auto.reset_auto_loop` como proceso dedicado junto con control, Modbus, ingesta, MQTT y monitor.
