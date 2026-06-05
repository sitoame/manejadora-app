# Checkpoint: supervisión de procesos y recuperación Modbus

## Cambios realizados por Codex

- Reemplacé el arranque lineal de procesos en `main.py` por una tabla de specs con nombre, target, args, política de restart, criticidad y contador de fallos.
- Añadí supervisión periódica en el loop principal para detectar procesos caídos con `proc.is_alive()`, programar restart con backoff exponencial y registrar cada evento.
- Incorporé límites configurables `process_restart_max_attempts`, `process_restart_backoff_seconds` y `process_restart_window_seconds` en settings y runtime config.
- Activé `safe_mode` con razón `process_failed:<name>` cuando un proceso crítico (`modbus` o `control`) supera el límite de fallos.
- Añadí recuperación explícita de puerto Modbus RTU/serial ante errores consecutivos: cierre, recreación de puerto, limpieza de estado de escritura y bloqueo de salidas hasta obtener una lectura válida.
- Reordené el ciclo Modbus para leer antes de escribir y evitar comandos de salida mientras el puerto no está recuperado.

## Validación

- Validación sintáctica con `ast.parse` sobre `main.py`, `func/modbus.py`, `func/runtime_config.py` y `var/const.py`.
