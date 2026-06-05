# 2026-06-05 systemd deployment

## Objetivo

Adaptar `deployment/systemd` para este repositorio `manejadora-app`, eliminando contenido heredado del proyecto PLC/UI copiado.

## Cambios

- Reemplazadas unidades `plc-*` por `manejadora-app.service.in` y `manejadora-app.target`.
- Eliminada la unidad UI/npm porque el monitor HTTP está integrado en `main.py`.
- Actualizados `install.sh` y `uninstall.sh` para renderizar e instalar solo el servicio Python actual.
- Agregado `manejadora-app.env.example` para overrides de autenticación y branding del monitor.
- Reescritos scripts operativos para usar `/api/runtime` del monitor actual.
- Actualizado `deployment/systemd/README.md` con operación, configuración y ejemplos del repo vigente.

## Validación ejecutada

- `bash -n deployment/systemd/install.sh deployment/systemd/uninstall.sh deployment/systemd/scripts/force_on.sh deployment/systemd/scripts/force_off.sh deployment/systemd/scripts/release_override.sh`
- `python3 -m compileall main.py func utilities var prueba_modbus.py regisssstttt.py`
- `systemd-analyze verify` sobre `manejadora-app.service.in` renderizado temporalmente y `manejadora-app.target`.
