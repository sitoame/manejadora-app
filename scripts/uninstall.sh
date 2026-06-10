#!/usr/bin/env bash
set -euo pipefail

SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
ENV_DIR="${ENV_DIR:-/etc/manejadora_app}"
SERVICE_NAME="manejadora_app.service"
TARGET_NAME="manejadora_app.target"
REMOVE_ENV="${REMOVE_ENV:-false}"

require_root() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || {
    echo "[ERR] run this uninstaller with sudo or as root" >&2
    exit 1
  }
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[ERR] missing command: $1" >&2
    exit 1
  }
}

require_root
require_cmd systemctl

for unit in "$TARGET_NAME" "$SERVICE_NAME"; do
  systemctl stop "$unit" 2>/dev/null || true
  systemctl disable "$unit" 2>/dev/null || true
  rm -f "$SYSTEMD_DIR/$unit"
done

if [[ "$REMOVE_ENV" == "true" ]]; then
  rm -rf "$ENV_DIR"
fi

systemctl daemon-reload
systemctl reset-failed "$SERVICE_NAME" "$TARGET_NAME" 2>/dev/null || true

echo "[INFO] removed systemd units: $SERVICE_NAME, $TARGET_NAME"
if [[ "$REMOVE_ENV" != "true" ]]; then
  echo "[INFO] kept env dir: $ENV_DIR"
fi
