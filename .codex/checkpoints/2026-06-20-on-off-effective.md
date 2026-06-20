# Separación estado solicitado/aplicado

- Se mantuvo `shared_state["on_off_global"]` como solicitud global/manual.
- Se agregó `shared_state["on_off_effective"]` como estado aplicado.
- Se centralizó el cálculo en `func/state.py` mediante `calculate_on_off_effective()` y `sync_on_off_effective()`.
- El calendario solo publica su señal en `shared_state["calendar"]` y solicita sincronización efectiva sin modificar la orden global.
- Control, ingesta, monitor y MQTT exponen la separación entre solicitud global, señal calendario y estado efectivo.
