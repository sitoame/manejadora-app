# Checkpoint Codex - reset_auto

## Cambios

- Integrado `func/reset_auto.py` al arranque multiproceso de `main.py`.
- Agregados defaults de configuración y estado compartido para reset automático.
- Habilitada edición runtime de parámetros `reset_auto_*`.
- Publicado el estado `reset_auto` en monitor HTTP y payload MQTT.
- Documentada la lógica operativa en `docs/reset_auto.md`.

## Validación

- `python3 -m compileall main.py func var`
- `python3 - <<'PY' ... create_shared_state + snapshot ... PY`
