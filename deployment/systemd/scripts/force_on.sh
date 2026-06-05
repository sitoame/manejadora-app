#!/usr/bin/env bash
set -euo pipefail

API="http://192.168.1.121:8080"

echo "$(date) START CHWP1_START" >> /home/maxia/hvac_force.log

curl -sS -X POST "$API/outputs/CHWP1_START/force" \
  -H "Content-Type: application/json" \
  -d '{"value":true,"source":"COMMISSIONING","reason":"scheduled start"}'

sleep 60

echo "$(date) START CH1_ENABLE" >> /home/maxia/hvac_force.log

curl -sS -X POST "$API/outputs/CH1_ENABLE/force" \
  -H "Content-Type: application/json" \
  -d '{"value":true,"source":"COMMISSIONING","reason":"scheduled start"}'

sleep 1200

echo "$(date) START CH2_ENABLE" >> /home/maxia/hvac_force.log

curl -sS -X POST "$API/outputs/CH2_ENABLE/force" \
  -H "Content-Type: application/json" \
  -d '{"value":true,"source":"COMMISSIONING","reason":"scheduled start"}'