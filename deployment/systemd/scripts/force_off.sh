#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://192.168.1.121:8090}"
TARGET="${1:-ahu_supply_fan_cmd}"
SOURCE="${SOURCE:-COMMISSIONING}"
TS="$(date -u +%s)"

curl -fsS -X POST "${API_BASE}/api/v1/outputs/${TARGET}/force" \
  -H "Content-Type: application/json" \
  -d "{\"value\":false,\"source\":\"${SOURCE}\",\"timestamp\":${TS},\"metadata\":{\"reason\":\"scheduled_force_off\"}}"
