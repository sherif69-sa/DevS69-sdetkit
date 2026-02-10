#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f .venv/bin/activate ] && [ -z "${VIRTUAL_ENV:-}" ]; then
  . .venv/bin/activate
fi

cmd=${1:-all}
spec=${2:-}

run_precommit() {
  i=0
  while :; do
    if pre-commit run -a; then
      return 0
    fi
    i=$((i + 1))
    if [ "$i" -ge 6 ]; then
      echo "pre-commit did not settle after $i runs" >&2
      return 1
    fi
  done
}

case "$cmd" in
  patch)
    python3 tools/patch_harness.py "$spec"
    ;;
  fmt)
    run_precommit
    ;;
  test)
    python3 -m pytest -q
    ;;
  all)
    if [ -n "$spec" ]; then
      python3 tools/patch_harness.py "$spec"
    fi
    run_precommit
    python3 -m pytest -q
    git status --porcelain
    ;;
  amend)
    git add -A
    git commit --amend --no-edit
    ;;
  push)
    git push --force-with-lease
    ;;
  doctor)
    PYTHONPATH=src python -m sdetkit.doctor --ascii
    ;;
  check)
    PYTHONPATH=src python -m sdetkit.doctor --ascii
    pre-commit run ruff-format -a
    pre-commit run ruff -a
    python -m pytest -q
    ;;
  *)
    echo "Usage: bash tools/devS69.sh {patch SPEC|fmt|test|all [SPEC]|amend|push}" >&2
    exit 2
    ;;
esac
