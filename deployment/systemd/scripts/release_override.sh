#!/usr/bin/env bash
set -euo pipefail

API="http://192.168.1.121:8080"

echo "$(date) START CH1_ENABLE" >> /home/maxia/hvac_force.log

curl -sS -X POST "$API/outputs/CH1_ENABLE/release" \
  -H "Content-Type: application/json" \
  -d '{"value":true,"source":"COMMISSIONING","reason":"scheduled stop"}'

echo "$(date) START CH2_ENABLE" >> /home/maxia/hvac_force.log

curl -sS -X POST "$API/outputs/CH2_ENABLE/release" \
  -H "Content-Type: application/json" \
  -d '{"value":true,"source":"COMMISSIONING","reason":"scheduled stop"}'

echo "$(date) START CHWP2_START" >> /home/maxia/hvac_force.log

sleep 120

curl -sS -X POST "$API/outputs/CHWP1_START/release" \
  -H "Content-Type: application/json" \
  -d '{"source":"COMMISSIONING","reason":"scheduled stop"}'
