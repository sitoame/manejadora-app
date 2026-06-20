# Refactor calendario/on_off_global

- `func/calendario.py` deja de escribir `shared_state["on_off_global"]` y publica solo en `shared_state["calendar"]`.
- `func/state.py` centraliza la combinación entre comando manual, estado de calendario y override manual.
- `func/control.py`, `func/ingesta.py`, `func/monitor.py`, `func/mqtt.py` y `func/runtime_config.py` consumen o actualizan el nuevo modelo de estado.
- `docs/calendario.md` documenta la prioridad efectiva y el modo `manual_override`.
