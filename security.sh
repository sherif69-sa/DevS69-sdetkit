#!/usr/bin/env bash
set -euo pipefail

if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
fi

mkdir -p build
python -m sdetkit security check --baseline tools/security.baseline.json --fail-on high --format text
python -m sdetkit security check --baseline tools/security.baseline.json --fail-on high --format sarif --output build/security.sarif
