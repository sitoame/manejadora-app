#!/usr/bin/env bash
set -euo pipefail

SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
ENV_DIR="${ENV_DIR:-/etc/manejadora_app}"
SERVICE_NAME="manejadora_app.service"
TARGET_NAME="manejadora_app.target"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="${APP_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
SERVICE_USER="${SERVICE_USER:-${SUDO_USER:-$(id -un)}}"
SERVICE_GROUP="${SERVICE_GROUP:-$(id -gn "$SERVICE_USER" 2>/dev/null || id -gn)}"
DEFAULT_PYTHON_BIN="$APP_ROOT/my_venv/bin/python3.12"
if [[ ! -x "$DEFAULT_PYTHON_BIN" ]]; then
  DEFAULT_PYTHON_BIN="$APP_ROOT/my_venv/bin/python"
fi
PYTHON_BIN="${PYTHON_BIN:-$DEFAULT_PYTHON_BIN}"
UNIT_TEMPLATE="$SCRIPT_DIR/$SERVICE_NAME.in"
TARGET_TEMPLATE="$SCRIPT_DIR/$TARGET_NAME"
ENV_TEMPLATE="$SCRIPT_DIR/manejadora_app.env.example"
ENV_FILE="$ENV_DIR/manejadora_app.env"
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

require_root() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || {
    echo "[ERR] run this installer with sudo or as root" >&2
    exit 1
  }
}

render_unit() {
  sed \
    -e "s#__APP_ROOT__#$APP_ROOT#g" \
    -e "s#__SERVICE_USER__#$SERVICE_USER#g" \
    -e "s#__SERVICE_GROUP__#$SERVICE_GROUP#g" \
    -e "s#__PYTHON_BIN__#$PYTHON_BIN#g" \
    -e "s#__ENV_FILE__#$ENV_FILE#g" \
    "$UNIT_TEMPLATE" > "$UNIT_TMP"
}

echo "[INFO] validating manejadora_app deployment"
require_root
require_cmd systemctl
require_cmd sed
require_cmd install
require_path "$UNIT_TEMPLATE"
require_path "$TARGET_TEMPLATE"
require_path "$ENV_TEMPLATE"
require_path "$APP_ROOT/main.py"
require_path "$APP_ROOT/requirements.txt"
require_path "$PYTHON_BIN"

mkdir -p "$APP_ROOT/logs" "$APP_ROOT/var" "$ENV_DIR"
if [[ ! -f "$ENV_FILE" ]]; then
  install -m 0640 "$ENV_TEMPLATE" "$ENV_FILE"
fi

render_unit

echo "[INFO] installing systemd units"
install -m 0644 "$UNIT_TMP" "$SYSTEMD_DIR/$SERVICE_NAME"
install -m 0644 "$TARGET_TEMPLATE" "$SYSTEMD_DIR/$TARGET_NAME"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME" "$TARGET_NAME"
systemctl restart "$SERVICE_NAME"

echo "[INFO] status"
systemctl --no-pager --full status "$SERVICE_NAME" || true

echo "[INFO] done"
echo "  journalctl -u $SERVICE_NAME -f"
echo "  systemctl restart $SERVICE_NAME"
echo "  systemctl stop $TARGET_NAME"
