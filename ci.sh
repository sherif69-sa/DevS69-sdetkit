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

run_gate_fast() {
  gate_args=()
  if [[ "$run_network" -eq 1 ]]; then
    gate_args+=(--pytest-args "-q -o addopts=")
  fi

  set +e
  rc=0
  if [[ "${artifact_dir}" != "" ]]; then
    mkdir -p "$artifact_dir"
    python3 -m sdetkit gate fast --format json --stable-json --out "$artifact_dir/gate-fast.json" "${gate_args[@]}"
    rc=$?
  fi
  python3 -m sdetkit gate fast "${gate_args[@]}"
  rc2=$?
  if [[ "$rc2" -ne 0 ]]; then
    rc=$rc2
  fi
  set -e
  return "$rc"
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
    run_gate_fast
    ;;
  all)
    run_gate_fast
    run_docs
    ;;
  *)
    echo "usage: $0 {all|quick} [--skip-docs] [--run-network] [--artifact-dir DIR]" >&2
    exit 2
    ;;
esac
