#!/usr/bin/env bash
set -euo pipefail

SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
ENV_DIR="${ENV_DIR:-/etc/manejadora-app}"
SERVICE_NAME="manejadora-app.service"
TARGET_NAME="manejadora-app.target"
REMOVE_ENV="${REMOVE_ENV:-false}"

for unit in "$TARGET_NAME" "$SERVICE_NAME"; do
  systemctl stop "$unit" 2>/dev/null || true
  systemctl disable "$unit" 2>/dev/null || true
  rm -f "$SYSTEMD_DIR/$unit"
done

if [[ "$REMOVE_ENV" == "true" ]]; then
  rm -rf "$ENV_DIR"
fi

systemctl daemon-reload

echo "[INFO] removed systemd units: $SERVICE_NAME, $TARGET_NAME"
if [[ "$REMOVE_ENV" != "true" ]]; then
  echo "[INFO] kept env dir: $ENV_DIR"
fi
