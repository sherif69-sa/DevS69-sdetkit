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
    python tools/patch_harness.py "$spec"
    ;;
  fmt)
    run_precommit
    ;;
  test)
    python -m pytest -q
    ;;
  all)
    if [ -n "$spec" ]; then
      python tools/patch_harness.py "$spec"
    fi
    run_precommit
    python -m pytest -q
    git status --porcelain
    ;;
  amend)
    git add -A
    git commit --amend --no-edit
    ;;
  push)
    GIT_SSH_COMMAND='ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes' git push --force-with-lease
    ;;
  *)
    echo "Usage: bash tools/devS69.sh {patch SPEC|fmt|test|all [SPEC]|amend|push}" >&2
    exit 2
    ;;
esac
