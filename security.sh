#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  :
elif [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
else
  bash scripts/bootstrap.sh
  # shellcheck disable=SC1091
  . .venv/bin/activate
fi

python3 scripts/check_repo_layout.py
python -m sdetkit security check --format text
