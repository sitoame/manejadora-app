# Checkpoint: política explícita calendario/operador

## Cambios
- Se agregó `schedule_mode` con modos `AUTO`, `MANUAL_ON` y `MANUAL_OFF`.
- `POWER` / `ON_OFF` ahora fijan modo manual explícito en vez de depender de un override implícito.
- El cálculo efectivo diferencia solicitud manual, solicitud calendario y salida efectiva.
- Runtime config persiste/restaura `schedule_mode`.
- Monitor, `/api/status` y status MQTT exponen la política efectiva.
- Se eliminaron archivos legacy `.old`/duplicados del árbol `func/`.

## Validación
- `python -m compileall func main.py` ejecutado correctamente.
- Assertions inline de transición `AUTO`/`MANUAL_ON`/`MANUAL_OFF` ejecutadas correctamente.
