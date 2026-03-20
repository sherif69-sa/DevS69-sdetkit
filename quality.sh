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

valid_modes=(all ci fmt lint type doctor test full-test cov mut muthtml boost)

mode_suggestion() {
  python3 - "$1" "${valid_modes[@]}" <<'PY'
import difflib
import sys

unknown = sys.argv[1]
choices = sys.argv[2:]
match = difflib.get_close_matches(unknown, choices, n=1)
if match:
    print(match[0])
PY
}

run_fmt()     { need_cmd ruff; python -m ruff format .; }
run_fmt_check() { need_cmd ruff; python -m ruff format --check .; }
run_lint()    { need_cmd ruff; python -m ruff check .; }
run_type()    { need_cmd mypy; python -m mypy --config-file pyproject.toml src; }
run_doctor()  { python -m sdetkit doctor --dev --ci --deps --repo --upgrade-audit --format md; }
run_gate_fast() { python -m sdetkit gate fast; }
run_premium_autofix() {
  if [[ -f "premium-gate.sh" ]]; then
    python -m sdetkit.premium_gate_engine \
      --out-dir .sdetkit/out \
      --double-check \
      --auto-fix \
      --auto-run-scripts \
      --format markdown
  else
    echo "skip premium auto-fix: premium-gate.sh not found"
  fi
}
run_premium_fast() {
  if [[ -f "premium-gate.sh" ]]; then
    bash premium-gate.sh --mode "${SDETKIT_BOOST_PREMIUM_MODE:-fast}"
  else
    echo "skip premium gate: premium-gate.sh not found"
  fi
}
run_topology_check() {
  local profile="${SDETKIT_BOOST_TOPOLOGY_PROFILE:-examples/kits/integration/heterogeneous-topology.json}"
  if [[ -f "$profile" ]]; then
    python -m sdetkit integration topology-check --profile "$profile"
  else
    echo "skip topology check: $profile not found"
  fi
}
run_optimize_summary() {
  python -m sdetkit kits optimize \
    --goal "${SDETKIT_BOOST_GOAL:-upgrade umbrella architecture with agentos optimization}" \
    --format text
}
run_boost() {
  run_doctor
  run_type
  run_premium_autofix
  run_gate_fast
  run_premium_fast
  run_topology_check
  run_optimize_summary
}
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
  doctor) run_doctor ;;
  test) run_gate_fast ;;
  cov) run_cov ;;
  full-test) run_full_test ;;
  mut) run_mut ;;
  muthtml) run_muthtml ;;
  boost) run_boost ;;
  ci)
    run_fmt_check
    run_lint
    run_type
    run_gate_fast
    ;;
  all)
    run_fmt
    run_lint
    run_type
    run_test
    run_cov
    ;;
  *)
    echo "Usage: bash quality.sh {all|ci|fmt|lint|type|doctor|test|full-test|cov|mut|muthtml|boost}" >&2
    suggestion="$(mode_suggestion "$mode" || true)"
    if [[ -n "$suggestion" ]]; then
      echo "Did you mean: bash quality.sh $suggestion" >&2
    fi
    exit 2
    ;;
esac
