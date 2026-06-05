#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8088}"
TARGET="${1:-fan}"
VALUE="${2:-true}"
MODE="${MODE:-MANUAL}"
MONITOR_AUTH_USER="${MONITOR_AUTH_USER:-dynatek}"
MONITOR_AUTH_PASSWORD="${MONITOR_AUTH_PASSWORD:-dynatek}"

payload="$({ python3 - "$TARGET" "$VALUE" "$MODE" <<'PY'
import json
import sys

target, raw_value, mode = sys.argv[1:4]
text = raw_value.strip().lower()
if text in {"true", "on", "1", "yes", "si"}:
    value = True
elif text in {"false", "off", "0", "no"}:
    value = False
else:
    try:
        value = float(raw_value)
    except ValueError:
        value = raw_value
print(json.dumps({"mode": mode, "manual_overrides": {target: value, f"{target}_forced": True}}))
PY
})"

curl -fsS -u "${MONITOR_AUTH_USER}:${MONITOR_AUTH_PASSWORD}" \
  -X POST "${API_BASE}/api/runtime" \
  -H "Content-Type: application/json" \
  -d "$payload"
