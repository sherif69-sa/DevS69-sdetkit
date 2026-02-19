#!/usr/bin/env bash

set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

if [ -d ".venv/bin" ]; then
  PATH="$root/.venv/bin:$PATH"
  export PATH
fi

mode=${1:-}

case "$mode" in
  fmt)
    shift || true
    ruff format "${@:-.}"
    ;;
  lint)
    ruff format --check .
    ruff check .
    ;;
  types)
    mypy src
    ;;
  tests)
    pytest
    ;;
  coverage)
    pytest --cov=src/sdetkit --cov-report=term-missing --cov-report=xml
    ;;
  docs)
    mkdocs build
    python scripts/check_onboarding_contract.py
    python scripts/check_day3_proof_contract.py
    python scripts/check_day4_skills_contract.py
    ;;
  onboarding)
    python scripts/check_onboarding_contract.py
    ;;
  day3)
    python scripts/check_day3_proof_contract.py
    ;;
  day4)
    python scripts/check_day4_skills_contract.py
    ;;
  all)
    ruff format --check .
    ruff check .
    mypy src
    pytest
    pytest --cov=src/sdetkit --cov-report=term-missing --cov-report=xml
    mkdocs build
    python scripts/check_onboarding_contract.py
    python scripts/check_day3_proof_contract.py
    python scripts/check_day4_skills_contract.py
    ;;
  *)
    echo "Usage: bash scripts/check.sh {fmt|lint|types|tests|coverage|docs|onboarding|day3|day4|all}" >&2
    exit 2
    ;;
esac

echo "All checks passed!"
