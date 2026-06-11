# Checkpoint Codex - Calendario operativo

## Cambios

- Integración del proceso `calendario_loop` en `main.py`.
- Inicialización de `shared_state["calendar"]` y evaluación previa al arranque de procesos.
- Exposición de `GET /api/horario` y `POST /api/horario` en el monitor HTTP.
- Persistencia del horario en `var/horario.json` mediante `horario_config_file`.
- Documentación operativa en `docs/calendario.md`.

## Validación sugerida

```bash
python3 -m py_compile main.py func/calendario.py func/monitor.py
```
