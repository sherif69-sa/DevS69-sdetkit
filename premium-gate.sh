#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

OUT_DIR=".sdetkit/out"
mkdir -p "$OUT_DIR"

section() {
  printf '\n==> %s\n' "$1"
}

warn() {
  printf '⚠️  %s\n' "$1"
}

info() {
  printf 'ℹ️  %s\n' "$1"
}

pass() {
  printf '✅ %s\n' "$1"
}

runtime_recommendation() {
  local title="$1"
  local elapsed="$2"
  case "$title" in
    "Quality")
      info "Recommendation: keep changed modules above baseline coverage to preserve premium quality." ;;
    "Ruff (format check)"|"Ruff (lint)")
      info "Recommendation: wire pre-commit hooks so lint and formatting warnings are caught before CI." ;;
    "CI")
      info "Recommendation: if CI is slow, shard tests by module while preserving deterministic ordering." ;;
    "Doctor JSON")
      info "Recommendation: review doctor output for high-severity checks first, then medium recommendations." ;;
    "Maintenance Full")
      info "Recommendation: prioritize failed maintenance checks with highest operational blast radius." ;;
    "Security Scan (offline SARIF)")
      info "Recommendation: fail on high severity findings in branch protection for production branches." ;;
    "Security Triage (baseline-aware)")
      info "Recommendation: keep baseline current to prevent warning fatigue and improve signal quality." ;;
    "Control Plane Ops (CI profile)")
      info "Recommendation: track ops profile drift in PR comments to maintain consistency across repos." ;;
    "Evidence Pack")
      info "Recommendation: attach evidence bundle to release candidates for audit-readiness." ;;
    "Premium Gate Engine")
      info "Recommendation: use premium-summary.json in PR comments to guide remediation priorities." ;;
  esac
  info "Real-time: '$title' completed in ${elapsed}s"
}

run_step() {
  local title="$1"
  shift
  local step_log="$OUT_DIR/premium-gate.$(echo "$title" | tr ' /()' '_____' | tr -cd '[:alnum:]_.-').log"
  section "$title"
  local started
  started="$(date +%s)"
  if ! "$@" 2>&1 | tee "$step_log"; then
    echo "ERROR: step failed: $title"
    warn "How to fix: run the same command locally, inspect logs under $OUT_DIR, and remediate before re-running premium-gate.sh."
    exit 1
  fi
  local ended elapsed
  ended="$(date +%s)"
  elapsed="$((ended - started))"
  pass "$title"
  runtime_recommendation "$title" "$elapsed"
}

run_step "Quality" bash quality.sh
run_step "Ruff (format check)" python3 -m ruff format --check .
run_step "Ruff (lint)" python3 -m ruff check .
run_step "CI" bash ci.sh
run_step "Doctor ASCII" python3 -m sdetkit doctor --ascii
run_step "Doctor JSON" python3 -m sdetkit doctor --json --out "$OUT_DIR/doctor.json"
run_step "Maintenance Full" python3 -m sdetkit maintenance --mode full --format json --out "$OUT_DIR/maintenance.json"
run_step "Security Scan (offline SARIF)" python3 -m sdetkit security scan --fail-on none --format sarif --output "$OUT_DIR/security.sarif"
run_step "Security Triage (baseline-aware)" python3 tools/triage.py --mode security --run-security --security-baseline tools/security.baseline.json --max-items 20 --tee "$OUT_DIR/security-check.json"
run_step "Control Plane Ops (CI profile)" python3 -m sdetkit ops run --profile ci --jobs 2
run_step "Evidence Pack" python3 -m sdetkit evidence pack --output "$OUT_DIR/evidence.zip"

section "Real-time warnings and recommendations summary"
run_step "Premium Gate Engine" python3 -m sdetkit.premium_gate_engine --out-dir "$OUT_DIR" --double-check --min-score 70 --auto-fix --fix-root "$ROOT_DIR" --learn-db --learn-commit --db-path "$OUT_DIR/premium-insights.db" --format text --json-output "$OUT_DIR/premium-summary.json"

echo "Premium gate passed. Artifacts: $OUT_DIR/doctor.json, $OUT_DIR/maintenance.json, $OUT_DIR/security.sarif, $OUT_DIR/security-check.json, $OUT_DIR/premium-summary.json, $OUT_DIR/evidence.zip"
