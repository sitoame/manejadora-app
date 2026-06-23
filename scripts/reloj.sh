#!/usr/bin/env bash
set -euo pipefail

TIMEZONE="${TIMEZONE:-America/Panama}"
CHRONY_CONF="/etc/chrony/chrony.conf"
HWCLOCK_SERVICE="/etc/systemd/system/hwclock.service"

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

install_chrony() {
  if command -v chronyd >/dev/null 2>&1 || command -v chrony >/dev/null 2>&1; then
    return
  fi

  require_cmd apt-get
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y chrony
}

configure_timezone() {
  timedatectl set-timezone "${TIMEZONE}"
}

configure_chrony() {
  install -d -m 0755 /etc/chrony /var/log/chrony
  cat > "${CHRONY_CONF}" <<'CHRONY_EOF'
# chrony cfg for RTC-backed systems
pool ntp.ubuntu.com        iburst maxsources 4
pool 0.ubuntu.pool.ntp.org iburst maxsources 1
pool 1.ubuntu.pool.ntp.org iburst maxsources 1
pool 2.ubuntu.pool.ntp.org iburst maxsources 2

keyfile /etc/chrony/chrony.keys
driftfile /var/lib/chrony/chrony.drift
logdir /var/log/chrony

maxupdateskew 100.0
rtcsync
makestep 1 -1
CHRONY_EOF
}

configure_hwclock_service() {
  systemctl stop hwclock.service >/dev/null 2>&1 || true
  systemctl disable hwclock.service >/dev/null 2>&1 || true

  cat > "${HWCLOCK_SERVICE}" <<'SERVICE_EOF'
[Unit]
Description=Save Hardware Clock
DefaultDependencies=no
Before=shutdown.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/hwclock --systohc

[Install]
WantedBy=shutdown.target
SERVICE_EOF

  systemctl daemon-reload
  systemctl enable hwclock.service
}

sync_clocks() {
  systemctl restart chrony
  chronyc makestep || true
  date
  hwclock --systohc
}

main() {
  require_root
  require_cmd systemctl
  require_cmd timedatectl

  install_chrony
  require_cmd chronyc
  require_cmd hwclock

  configure_timezone
  configure_chrony
  configure_hwclock_service
  sync_clocks

  systemctl --no-pager status hwclock.service || true
}

main "$@"
