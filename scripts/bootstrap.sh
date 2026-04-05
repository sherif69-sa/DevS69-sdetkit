#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ] || [ ! -f .venv/bin/activate ]; then
  rm -rf .venv
  python3 -m venv .venv
fi

.venv/bin/python -m pip install -c constraints-ci.txt -r requirements-test.txt -r requirements-docs.txt -e .
