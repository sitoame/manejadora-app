#!/usr/bin/env bash
set -euo pipefail

SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
ENV_DIR="${ENV_DIR:-/etc/manejadora-app}"
SERVICE_NAME="manejadora-app.service"
TARGET_NAME="manejadora-app.target"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="${APP_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
SERVICE_USER="${SERVICE_USER:-${SUDO_USER:-$(id -un)}}"
SERVICE_GROUP="${SERVICE_GROUP:-$(id -gn "$SERVICE_USER" 2>/dev/null || id -gn)}"
PYTHON_BIN="${PYTHON_BIN:-$APP_ROOT/.venv/bin/python3.12}"
UNIT_TEMPLATE="$SCRIPT_DIR/$SERVICE_NAME.in"
UNIT_TMP="$(mktemp)"

cleanup() {
  rm -f "$UNIT_TMP"
}
trap cleanup EXIT

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

render_unit() {
  sed \
    -e "s#__APP_ROOT__#$APP_ROOT#g" \
    -e "s#__SERVICE_USER__#$SERVICE_USER#g" \
    -e "s#__SERVICE_GROUP__#$SERVICE_GROUP#g" \
    -e "s#__PYTHON_BIN__#$PYTHON_BIN#g" \
    "$UNIT_TEMPLATE" > "$UNIT_TMP"
}

echo "[INFO] validating manejadora-app deployment"
require_cmd systemctl
require_cmd sed
require_path "$UNIT_TEMPLATE"
require_path "$SCRIPT_DIR/$TARGET_NAME"
require_path "$SCRIPT_DIR/manejadora-app.env.example"
require_path "$APP_ROOT/main.py"
require_path "$APP_ROOT/requirements.txt"
require_path "$PYTHON_BIN"

mkdir -p "$APP_ROOT/logs" "$APP_ROOT/var" "$ENV_DIR"
if [[ ! -f "$ENV_DIR/manejadora-app.env" ]]; then
  install -m 0640 "$SCRIPT_DIR/manejadora-app.env.example" "$ENV_DIR/manejadora-app.env"
fi

render_unit

echo "[INFO] installing systemd units"
install -m 0644 "$UNIT_TMP" "$SYSTEMD_DIR/$SERVICE_NAME"
install -m 0644 "$SCRIPT_DIR/$TARGET_NAME" "$SYSTEMD_DIR/$TARGET_NAME"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME" "$TARGET_NAME"
systemctl restart "$SERVICE_NAME"

echo "[INFO] status"
systemctl --no-pager --full status "$SERVICE_NAME" || true

echo "[INFO] done"
echo "  journalctl -u $SERVICE_NAME -f"
echo "  systemctl restart $SERVICE_NAME"
echo "  systemctl stop $TARGET_NAME"
