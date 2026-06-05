#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8088}"
TARGET="${1:-fan}"
MODE="${MODE:-AUTO}"
MONITOR_AUTH_USER="${MONITOR_AUTH_USER:-dynatek}"
MONITOR_AUTH_PASSWORD="${MONITOR_AUTH_PASSWORD:-dynatek}"

payload="$({ python3 - "$TARGET" "$MODE" <<'PY'
import json
import sys

target, mode = sys.argv[1:3]
print(json.dumps({"mode": mode, "manual_overrides": {f"{target}_forced": False}}))
PY
})"

curl -fsS -u "${MONITOR_AUTH_USER}:${MONITOR_AUTH_PASSWORD}" \
  -X POST "${API_BASE}/api/runtime" \
  -H "Content-Type: application/json" \
  -d "$payload"
