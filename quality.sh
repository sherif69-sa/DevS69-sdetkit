#!/usr/bin/env bash
set -euo pipefail
python3 scripts/check_repo_layout.py

mode=${1:-all}
cov_fail_under=${COV_FAIL_UNDER:-70}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 && return 0
  echo "missing tool: $1" >&2
  echo "hint: activate a venv and run: python -m pip install -e '.[dev,test,docs]'" >&2
  exit 127
}

run_fmt()     { need_cmd ruff; python -m ruff format .; }
run_lint()    { need_cmd ruff; python -m ruff check .; }
run_type()    { need_cmd mypy; python -m mypy --config-file pyproject.toml src; }
run_test()    { need_cmd pytest; python -m pytest; }
run_cov()     { need_cmd pytest; python -m pytest --cov=sdetkit --cov-report=term-missing --cov-fail-under="$cov_fail_under"; }
run_mut()     { need_cmd mutmut; mutmut run; }
run_muthtml() { need_cmd mutmut; mutmut html; }

case "$mode" in
  fmt) run_fmt ;;
  lint) run_lint ;;
  type) run_type ;;
  test) run_test ;;
  cov) run_cov ;;
  mut) run_mut ;;
  muthtml) run_muthtml ;;
  all)
    run_fmt
    run_lint
    run_type
    run_test
    run_cov
    ;;
  *)
    echo "Usage: bash quality.sh {all|fmt|lint|type|test|cov|mut|muthtml}" >&2
    exit 2
    ;;
esac
