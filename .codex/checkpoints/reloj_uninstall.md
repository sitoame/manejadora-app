# Codex checkpoint: reloj uninstall

- Renombrado el instalador de reloj de `scripts/reloj.sh` a `scripts/reloj_install.sh`.
- Agregado `scripts/reloj.uninstall.sh` para remover el servicio `hwclock.service` creado por el instalador.
- El uninstall conserva por defecto la configuración de chrony y permite borrarla con `REMOVE_CHRONY_CONF=true`.
- El uninstall permite purgar chrony explícitamente con `PURGE_CHRONY=true`.
- Documentado el flujo de instalación/desinstalación de reloj en `scripts/README.md`.
