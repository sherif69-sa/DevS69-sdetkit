#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

section() {
  printf '\n==> %s\n' "$1"
}

run_step() {
  local title="$1"
  shift
  section "$title"
  if ! "$@"; then
    echo "ERROR: step failed: $title"
    echo "How to fix: run the same command locally, inspect logs under .sdetkit/out/, and remediate before re-running premium-gate.sh."
    exit 1
  fi
}

run_step "Quality" bash quality.sh
run_step "Ruff (format check)" python3 -m ruff format --check .
run_step "Ruff (lint)" python3 -m ruff check .
run_step "CI" bash ci.sh
run_step "Doctor ASCII" python3 -m sdetkit doctor --ascii
run_step "Maintenance Full" python3 -m sdetkit maintenance --mode full --format json --out .sdetkit/out/maintenance.json
run_step "Security Scan (offline SARIF)" python3 -m sdetkit security scan --fail-on none --format sarif --output .sdetkit/out/security.sarif
run_step "Security Triage (baseline-aware)" python3 tools/triage.py --mode security --run-security --security-baseline tools/security.baseline.json --max-items 20 --tee .sdetkit/out/security-check.json
run_step "Control Plane Ops (CI profile)" python3 -m sdetkit ops run --profile ci --jobs 2
run_step "Evidence Pack" python3 -m sdetkit evidence pack --output .sdetkit/out/evidence.zip

echo "Premium gate passed. Artifacts: .sdetkit/out/maintenance.json, .sdetkit/out/security.sarif, .sdetkit/out/security-check.json, .sdetkit/out/evidence.zip"
