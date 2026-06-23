#!/usr/bin/env bash
set -euo pipefail

CHRONY_CONF="${CHRONY_CONF:-/etc/chrony/chrony.conf}"
HWCLOCK_SERVICE="${HWCLOCK_SERVICE:-/etc/systemd/system/hwclock.service}"
REMOVE_CHRONY_CONF="${REMOVE_CHRONY_CONF:-false}"
PURGE_CHRONY="${PURGE_CHRONY:-false}"

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "Ejecuta este script como root: sudo $0" >&2
    exit 1
  fi
}

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Comando requerido no disponible: ${cmd}" >&2
    exit 1
  fi
}

remove_hwclock_service() {
  systemctl stop hwclock.service >/dev/null 2>&1 || true
  systemctl disable hwclock.service >/dev/null 2>&1 || true
  rm -f "${HWCLOCK_SERVICE}"
}

remove_chrony_conf() {
  if [[ "${REMOVE_CHRONY_CONF}" != "true" ]]; then
    return
  fi

  rm -f "${CHRONY_CONF}"
}

purge_chrony() {
  if [[ "${PURGE_CHRONY}" != "true" ]]; then
    return
  fi

  require_cmd apt-get
  systemctl stop chrony >/dev/null 2>&1 || true
  DEBIAN_FRONTEND=noninteractive apt-get purge -y chrony
  DEBIAN_FRONTEND=noninteractive apt-get autoremove -y
}

main() {
  require_root
  require_cmd systemctl

  remove_hwclock_service
  remove_chrony_conf
  purge_chrony

  systemctl daemon-reload
  systemctl reset-failed hwclock.service chrony.service >/dev/null 2>&1 || true

  echo "[INFO] removed hwclock systemd service: ${HWCLOCK_SERVICE}"
  if [[ "${REMOVE_CHRONY_CONF}" == "true" ]]; then
    echo "[INFO] removed chrony config: ${CHRONY_CONF}"
  else
    echo "[INFO] kept chrony config: ${CHRONY_CONF}"
  fi
  if [[ "${PURGE_CHRONY}" == "true" ]]; then
    echo "[INFO] purged chrony package"
  fi
}

main "$@"
