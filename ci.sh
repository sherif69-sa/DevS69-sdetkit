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

mode="${1:-all}"
shift || true

skip_docs=0
run_network=0
artifact_dir=""

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --skip-docs)
      skip_docs=1
      shift
      ;;
    --run-network)
      run_network=1
      shift
      ;;
    --artifact-dir)
      if [[ "${2:-}" == "" ]]; then
        echo "missing value for --artifact-dir" >&2
        echo "usage: $0 {all|quick} [--skip-docs] [--run-network] [--artifact-dir DIR]" >&2
        exit 2
      fi
      artifact_dir="$2"
      shift 2
      ;;
    *)
      echo "unknown option: $1" >&2
      echo "usage: $0 {all|quick} [--skip-docs] [--run-network] [--artifact-dir DIR]" >&2
      exit 2
      ;;
  esac
done

if [[ "${VIRTUAL_ENV:-}" == "" ]]; then
  echo "error: no virtualenv active" >&2
  echo "hint: bash scripts/bootstrap.sh && . .venv/bin/activate" >&2
  exit 2
fi

run_test_bootstrap_preflight() {
  local contract_args=(--strict --format json)
  local runtime_args=(--strict --format json)
  if [[ "${artifact_dir}" != "" ]]; then
    mkdir -p "$artifact_dir"
    contract_args+=(--out "$artifact_dir/test-bootstrap-contract.json")
    runtime_args+=(--out "$artifact_dir/test-bootstrap-runtime.json")
  fi
  PYTHONPATH=src python3 -m sdetkit.test_bootstrap_contract "${contract_args[@]}"
  PYTHONPATH=src python3 -m sdetkit.test_bootstrap_validate "${runtime_args[@]}"
}

run_gate_fast() {
  gate_args=()
  if [[ "$run_network" -eq 1 ]]; then
    gate_args+=(--pytest-args "-q -o addopts=")
  fi

  set +e
  rc=0
  if [[ "${artifact_dir}" != "" ]]; then
    mkdir -p "$artifact_dir"
    python3 -m sdetkit gate fast --no-mypy --format json --stable-json --out "$artifact_dir/gate-fast.json" "${gate_args[@]}"
    rc=$?
  fi
  python3 -m sdetkit gate fast --no-mypy "${gate_args[@]}"
  rc2=$?
  if [[ "$rc2" -ne 0 ]]; then
    rc=$rc2
  fi
  set -e
  return "$rc"
}


run_flagship_contracts() {
  python3 -m sdetkit intelligence flake classify --history examples/kits/intelligence/flake-history.json >/dev/null
  python3 -m sdetkit intelligence failure-fingerprint --failures examples/kits/intelligence/failures.json >/dev/null
  python3 -m sdetkit integration check --profile examples/kits/integration/profile.json >/dev/null || true
  python3 -m sdetkit integration topology-check --profile examples/kits/integration/heterogeneous-topology.json >/dev/null
  python3 -m sdetkit forensics compare --from examples/kits/forensics/run-a.json --to examples/kits/forensics/run-b.json >/dev/null
}

run_docs() {
  if [[ "$skip_docs" -eq 1 ]]; then
    return 0
  fi
  if command -v mkdocs >/dev/null 2>&1; then
    NO_MKDOCS_2_WARNING=1 mkdocs build -s
    return 0
  fi
  NO_MKDOCS_2_WARNING=1 python3 -m mkdocs build -s
}

run_operational_maturity_v2() {
  mkdir -p .sdetkit/out
  set +e
  python3 scripts/legacy_command_analyzer.py --format json > .sdetkit/out/legacy-command-analyzer.json
  legacy_rc=$?
  set -e
  if [[ "$legacy_rc" -ne 0 && "$legacy_rc" -ne 2 ]]; then
    return "$legacy_rc"
  fi
  python3 scripts/legacy_burndown.py \
    --current .sdetkit/out/legacy-command-analyzer.json \
    --baseline-from-history .sdetkit/out/legacy-history \
    --json-out .sdetkit/out/legacy-burndown.json \
    --md-out .sdetkit/out/legacy-burndown.md \
    --csv-out .sdetkit/out/legacy-burndown.csv \
    --format json >/dev/null
  mkdir -p .sdetkit/out/legacy-history
  cp .sdetkit/out/legacy-command-analyzer.json ".sdetkit/out/legacy-history/legacy-command-analyzer-$(date +%Y%m%d%H%M%S).json"
  python3 scripts/adoption_scorecard.py --format json --out .sdetkit/out/adoption-scorecard.json >/dev/null
  python3 scripts/check_adoption_scorecard_v2_contract.py --infile .sdetkit/out/adoption-scorecard.json --format json >/dev/null
}

case "$mode" in
  quick)
    run_test_bootstrap_preflight
    run_gate_fast
    run_flagship_contracts
    run_operational_maturity_v2
    ;;
  all)
    run_test_bootstrap_preflight
    run_gate_fast
    run_flagship_contracts
    run_operational_maturity_v2
    run_docs
    ;;
  *)
    echo "usage: $0 {all|quick} [--skip-docs] [--run-network] [--artifact-dir DIR]" >&2
    exit 2
    ;;
esac
