#!/usr/bin/env bash
set -euo pipefail

mode=${1:-all}

py=${PYTHON:-python}
if ! command -v "$py" >/dev/null 2>&1; then
  py=python3
fi

run_lint() {
  ruff check .
  ruff format --check .
}

run_types() {
  mypy src/sdetkit
}

run_tests() {
  pytest -q
}

run_coverage() {
  cov=${COV_FAIL_UNDER:-0}
  pytest -q --cov=src/sdetkit --cov-report=term-missing --cov-report=xml --cov-fail-under="$cov"
}

run_docs() {
  mkdocs build --strict
}

case "$mode" in
  lint) run_lint ;;
  types) run_types ;;
  tests) run_tests ;;
  coverage) run_coverage ;;
  docs) run_docs ;;
  all)
    run_lint
    run_types
    run_tests
    run_coverage
    run_docs
    ;;
  *)
    echo "Usage: bash scripts/check.sh {lint|types|tests|coverage|docs|all}" >&2
    exit 2
    ;;
esac
