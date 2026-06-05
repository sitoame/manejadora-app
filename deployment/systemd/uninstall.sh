#!/usr/bin/env bash
set -euo pipefail

SYSTEMD_DIR="/etc/systemd/system"
ENGINE_SERVICE="plc-engine.service"
UI_SERVICE="plc-ui.service"
APP_TARGET="plc-app.target"

for unit in "$APP_TARGET" "$UI_SERVICE" "$ENGINE_SERVICE"; do
  systemctl stop "$unit" 2>/dev/null || true
  systemctl disable "$unit" 2>/dev/null || true
  rm -f "$SYSTEMD_DIR/$unit"
done

systemctl daemon-reload

echo "[INFO] removed systemd units: $ENGINE_SERVICE, $UI_SERVICE, $APP_TARGET"
