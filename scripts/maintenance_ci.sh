#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-full}"
FIX="${2:-false}"
OUT_PREFIX="${3:-artifacts/maintenance}"

mkdir -p artifacts

run_maintenance() {
  local mode="$1"
  local fix_flag="$2"
  local fmt="$3"
  local out="$4"
  local args=(python -m sdetkit.maintenance --mode "$mode" --format "$fmt" --out "$out" --quiet)
  if [[ "$fix_flag" == "true" ]]; then
    args+=(--fix)
  fi
  set +e
  "${args[@]}"
  local rc=$?
  set -e
  if [[ "$rc" -eq 2 ]]; then
    echo "maintenance execution error for $out" >&2
    exit 2
  fi
}

run_maintenance "$MODE" false json "${OUT_PREFIX}.json"
run_maintenance "$MODE" false md "${OUT_PREFIX}.md"

if [[ "$FIX" == "true" ]]; then
  run_maintenance "$MODE" true json artifacts/maintenance_fixed.json
  run_maintenance "$MODE" true md artifacts/maintenance_fixed.md
fi

python - <<'PY'
import json
from pathlib import Path

report = json.loads(Path('artifacts/maintenance.json').read_text(encoding='utf-8'))
failing = sorted([name for name, item in report['checks'].items() if not item['ok']])
print(f"score={report['score']}")
print("failing=" + (", ".join(failing) if failing else "none"))
PY

if ! git diff --quiet; then
  echo "has_diff=true"
else
  echo "has_diff=false"
fi
