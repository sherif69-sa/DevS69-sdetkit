#!/usr/bin/env bash
set -euo pipefail

ensure_venv() {
  if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    return 0
  fi

  if [[ -f ".venv/bin/activate" ]]; then
    . .venv/bin/activate
    return 0
  fi

  bash scripts/bootstrap.sh
  . .venv/bin/activate
}

ensure_venv
python3 scripts/check_repo_layout.py

mode=${1:-all}
# Keep the default gate realistic for full-repo runs, while still allowing
# stricter enforcement in CI/release jobs via COV_FAIL_UNDER=95.
cov_fail_under=${COV_FAIL_UNDER:-80}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 && return 0
  echo "missing tool: $1" >&2
  echo "hint: bash scripts/bootstrap.sh && . .venv/bin/activate" >&2
  exit 127
}

run_fmt()     { need_cmd ruff; python -m ruff format .; }
run_lint()    { need_cmd ruff; python -m ruff check .; }
run_type()    { need_cmd mypy; python -m mypy --config-file pyproject.toml src; }
run_gate_fast() { python -m sdetkit gate fast; }
run_full_test() { need_cmd pytest; python -m pytest -q -o addopts=; }
run_test()    { need_cmd pytest; python -m pytest; }
run_cov() {
  need_cmd pytest
  # Coverage profiles:
  # - full: complete repository visibility (informational)
  # - core (default): strict gate on critical, stable modules
  cov_scope="${COV_SCOPE:-core}"

  if [[ "$cov_scope" == "full" ]]; then
    python -m pytest --cov=sdetkit --cov-report=term-missing --cov-fail-under="$cov_fail_under"
    return
  fi

  python -m pytest \
    --cov=sdetkit.__main__ \
    --cov=sdetkit._entrypoints \
    --cov=sdetkit._toml \
    --cov=sdetkit.atomicio \
    --cov=sdetkit.report \
    --cov=sdetkit.reliability_evidence_pack \
    --cov=sdetkit.roadmap_manifest \
    --cov=sdetkit.sqlite_scalar \
    --cov=sdetkit.textutil \
    --cov-report=term-missing \
    --cov-fail-under="$cov_fail_under"
}
run_mut()     { need_cmd mutmut; mutmut run; }
run_muthtml() { need_cmd mutmut; mutmut html; }

case "$mode" in
  fmt) run_fmt ;;
  lint) run_lint ;;
  type) run_type ;;
  test) run_gate_fast ;;
  cov) run_cov ;;
  full-test) run_full_test ;;
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
    echo "Usage: bash quality.sh {all|fmt|lint|type|test|full-test|cov|mut|muthtml}" >&2
    exit 2
    ;;
esac
