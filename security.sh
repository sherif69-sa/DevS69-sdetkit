#!/usr/bin/env bash
set -euo pipefail

if [ -f .venv/bin/activate ]; then
  . .venv/bin/activate
fi

mkdir -p build

python -m sdetkit security scan --format json --output build/security-scan.json --fail-on none
python -m sdetkit security check --scan-json build/security-scan.json --baseline tools/security.baseline.json --fail-on high --format text
python -m sdetkit security check --scan-json build/security-scan.json --baseline tools/security.baseline.json --fail-on high --format sarif --output build/security.sarif
