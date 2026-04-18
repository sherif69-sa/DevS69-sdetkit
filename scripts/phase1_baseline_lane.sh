#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-build/phase1-baseline}"
mkdir -p "${OUT_DIR}" "${OUT_DIR}/logs"

PHASE1_OUT_DIR="${OUT_DIR}" python - <<'PY'
import sys
if sys.version_info < (3, 11):
    print(f"phase1-baseline: requires Python >=3.11 (detected {sys.version.split()[0]})")
    raise SystemExit(2)
PY

run_and_capture() {
  local name="$1"
  shift
  echo "[phase1-baseline] RUN ${name}: $*"
  set +e
  "$@" >"${OUT_DIR}/logs/${name}.out.log" 2>"${OUT_DIR}/logs/${name}.err.log"
  local rc=$?
  set -e
  echo "${rc}" >"${OUT_DIR}/logs/${name}.rc"
  if [[ ${rc} -eq 0 ]]; then
    echo "[phase1-baseline] OK  ${name}"
  else
    echo "[phase1-baseline] FAIL ${name} (rc=${rc})"
  fi
}

run_and_capture gate_fast \
  python -m sdetkit gate fast --format json --stable-json --out "${OUT_DIR}/gate-fast.json"
run_and_capture gate_release \
  python -m sdetkit gate release --format json --out "${OUT_DIR}/release-preflight.json"
run_and_capture doctor \
  python -m sdetkit doctor --format json --out "${OUT_DIR}/doctor.json"
run_and_capture enterprise_contracts \
  python scripts/validate_enterprise_contracts.py
run_and_capture primary_docs_map \
  python scripts/check_primary_docs_map.py
run_and_capture ruff \
  ruff check .
run_and_capture pytest \
  env PYTHONPATH=src pytest -q

python - <<'PY'
from __future__ import annotations

import json
from datetime import datetime, UTC
from pathlib import Path

import os

out_dir = Path(os.environ["PHASE1_OUT_DIR"])
logs = out_dir / "logs"

checks = [
    "gate_fast",
    "gate_release",
    "doctor",
    "enterprise_contracts",
    "primary_docs_map",
    "ruff",
    "pytest",
]

summary = {
    "schema_version": "sdetkit.phase1_baseline.v1",
    "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "out_dir": out_dir.as_posix(),
    "checks": [],
}

all_ok = True
for check in checks:
    rc_file = logs / f"{check}.rc"
    rc = int(rc_file.read_text().strip()) if rc_file.exists() else 99
    ok = rc == 0
    all_ok = all_ok and ok
    summary["checks"].append(
        {
            "id": check,
            "ok": ok,
            "rc": rc,
            "stdout_log": (logs / f"{check}.out.log").as_posix(),
            "stderr_log": (logs / f"{check}.err.log").as_posix(),
        }
    )

summary["ok"] = all_ok
(out_dir / "phase1-baseline-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

lines = [
    "# Phase 1 Baseline Lane Summary",
    "",
    f"- generated_at_utc: `{summary['generated_at_utc']}`",
    f"- overall_status: `{'OK' if summary['ok'] else 'FAIL'}`",
    f"- out_dir: `{summary['out_dir']}`",
    "",
    "## Checks",
]
for item in summary["checks"]:
    status = "OK" if item["ok"] else "FAIL"
    lines.append(f"- `{item['id']}`: **{status}** (rc={item['rc']})")

(out_dir / "phase1-baseline-summary.md").write_text("\n".join(lines) + "\n")
PY

echo "[phase1-baseline] Summary: ${OUT_DIR}/phase1-baseline-summary.json"
echo "[phase1-baseline] Summary: ${OUT_DIR}/phase1-baseline-summary.md"
