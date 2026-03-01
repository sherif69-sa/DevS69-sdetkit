#!/usr/bin/env bash
set -euo pipefail
python3 scripts/check_repo_layout.py

mode="${1:-all}"
shift || true

skip_docs=0
for arg in "$@"; do
  case "$arg" in
    --skip-docs) skip_docs=1 ;;
    *)
      echo "unknown option: $arg" >&2
      echo "usage: $0 {all|quick} [--skip-docs]" >&2
      exit 2
      ;;
  esac
done

if [[ "${VIRTUAL_ENV:-}" == "" ]]; then
  echo "error: no virtualenv active" >&2
  echo "hint: python3 -m venv .venv && . .venv/bin/activate && python -m pip install -e '.[dev,test,docs]'" >&2
  exit 2
fi

run_format() {
  python3 -m ruff format --check .
}

run_lint() {
  python3 -m ruff check .
}

run_types() {
  python3 -m mypy src
}

run_tests() {
  python3 -m pytest -q
}

run_docs() {
  if [[ "$skip_docs" -eq 1 ]]; then
    return 0
  fi
  if command -v mkdocs >/dev/null 2>&1; then
    mkdocs build -s
    return 0
  fi
  python3 -m mkdocs build -s
}

case "$mode" in
  quick)
    run_format
    run_lint
    run_types
    run_tests
    ;;
  all)
    run_format
    run_lint
    run_types
    run_tests
    run_docs
    ;;
  *)
    echo "usage: $0 {all|quick} [--skip-docs]" >&2
    exit 2
    ;;
esac
