#!/usr/bin/env bash
set -euo pipefail

SYSTEMD_DIR="/etc/systemd/system"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT_DEFAULT="/home/maxia/plc_app"
APP_ROOT="${APP_ROOT:-$APP_ROOT_DEFAULT}"

ENGINE_SERVICE="plc-engine.service"
UI_SERVICE="plc-ui.service"
APP_TARGET="plc-app.target"

ENGINE_ENV_SRC="$SCRIPT_DIR/plc-engine.env.example"
UI_ENV_SRC="$SCRIPT_DIR/plc-ui.env.example"
ENGINE_ENV_DST="$APP_ROOT/deployment/systemd/plc-engine.env"
UI_ENV_DST="$APP_ROOT/deployment/systemd/plc-ui.env"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[ERR] missing command: $1" >&2
    exit 1
  }
}

require_path() {
  [[ -e "$1" ]] || {
    echo "[ERR] missing required path: $1" >&2
    exit 1
  }
}

echo "[INFO] validating prerequisites"
require_cmd systemctl
require_cmd npm
require_path "$APP_ROOT/.venv/bin/python3.10"
require_path "$APP_ROOT/plc_hvac/app/main.py"
require_path "$APP_ROOT/commissioning_ui/package.json"

mkdir -p "$APP_ROOT/deployment/systemd"
[[ -f "$ENGINE_ENV_DST" ]] || cp "$ENGINE_ENV_SRC" "$ENGINE_ENV_DST"
[[ -f "$UI_ENV_DST" ]] || cp "$UI_ENV_SRC" "$UI_ENV_DST"

echo "[INFO] installing systemd units"
install -m 0644 "$SCRIPT_DIR/$ENGINE_SERVICE" "$SYSTEMD_DIR/$ENGINE_SERVICE"
install -m 0644 "$SCRIPT_DIR/$UI_SERVICE" "$SYSTEMD_DIR/$UI_SERVICE"
install -m 0644 "$SCRIPT_DIR/$APP_TARGET" "$SYSTEMD_DIR/$APP_TARGET"

systemctl daemon-reload
systemctl enable "$ENGINE_SERVICE" "$UI_SERVICE" "$APP_TARGET"
systemctl start "$APP_TARGET"

echo "[INFO] basic status"
systemctl --no-pager --full status "$ENGINE_SERVICE" || true
systemctl --no-pager --full status "$UI_SERVICE" || true

echo "[INFO] done"
echo "  journalctl -u $ENGINE_SERVICE -f"
echo "  journalctl -u $UI_SERVICE -f"
echo "  systemctl restart $APP_TARGET"
