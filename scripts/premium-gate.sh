#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${SDETKIT_PREMIUM_OUT_DIR:-.sdetkit/out}"
MODE="${SDETKIT_PREMIUM_MODE:-full}"
CONTINUE_ON_ERROR=0
ENGINE_MIN_SCORE="${SDETKIT_PREMIUM_MIN_SCORE:-70}"
OPS_JOBS="${SDETKIT_PREMIUM_OPS_JOBS:-2}"
TOPOLOGY_PROFILE="${SDETKIT_PREMIUM_TOPOLOGY_PROFILE:-examples/kits/integration/heterogeneous-topology.json}"
AUTO_RUN_SCRIPTS="${SDETKIT_PREMIUM_AUTO_RUN_SCRIPTS:-1}"
SCRIPT_CATALOG="${SDETKIT_PREMIUM_SCRIPT_CATALOG:-.sdetkit/premium-remediation-scripts.json}"

usage() {
  cat <<'USAGE'
Usage: bash premium-gate.sh [options]

Options:
  --mode <full|fast|engine-only>   Run profile: fast=honest smoke confidence, full=merge/release truth via `bash quality.sh verify` (default: full)
  --out-dir <path>                 Artifact/log directory (default: .sdetkit/out)
  --engine-min-score <int>         Minimum premium engine score (default: 70)
  --ops-jobs <int>                 Parallel jobs for ops run (default: 2)
  --no-auto-run-scripts            Disable smart remediation script execution inside the premium engine
  --script-catalog <path>          Override the premium remediation script catalog
  --continue-on-error              Continue collecting evidence after a failing step
  -h, --help                       Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    --engine-min-score)
      ENGINE_MIN_SCORE="${2:-}"
      shift 2
      ;;
    --ops-jobs)
      OPS_JOBS="${2:-}"
      shift 2
      ;;
    --continue-on-error)
      CONTINUE_ON_ERROR=1
      shift
      ;;
    --script-catalog)
      SCRIPT_CATALOG="${2:-}"
      shift 2
      ;;
    --no-auto-run-scripts)
      AUTO_RUN_SCRIPTS=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$MODE" in
  full|fast|engine-only) ;;
  *)
    echo "Invalid --mode: $MODE (expected full|fast|engine-only)" >&2
    exit 2
    ;;
esac

mkdir -p "$OUT_DIR"
STEP_INDEX_JSON="$OUT_DIR/premium-step-index.json"
STEP_RESULTS_NDJSON="$OUT_DIR/premium-step-results.ndjson"
PREMIUM_VERDICT_JSON="$OUT_DIR/premium-verdict.json"
PREMIUM_SUMMARY_MD="$OUT_DIR/premium-summary.md"
PREMIUM_FIX_PLAN_JSON="$OUT_DIR/premium-fix-plan.json"
PREMIUM_RISK_SUMMARY_JSON="$OUT_DIR/premium-risk-summary.json"
PREMIUM_EVIDENCE_ZIP="$OUT_DIR/premium-evidence.zip"
: > "$STEP_RESULTS_NDJSON"

section() { printf '\n==> %s\n' "$1"; }
warn() { printf '⚠️  %s\n' "$1"; }
info() { printf 'ℹ️  %s\n' "$1"; }
pass() { printf '✅ %s\n' "$1"; }

runtime_recommendation() {
  local title="$1"
  local elapsed="$2"
  case "$title" in
    "Quality (fast/smoke)") info "Recommendation: use this fast/smoke lane for local confidence only; run full verification before merge." ;;
    "Quality (full verification)") info "Recommendation: treat this full verification lane as the pre-merge truth path and fix failures before merge." ;;
    "Ruff (format check)"|"Ruff (lint)") info "Recommendation: wire pre-commit hooks so lint and formatting warnings are caught before CI." ;;
    "CI") info "Recommendation: if CI is slow, shard tests by module while preserving deterministic ordering." ;;
    "Doctor JSON") info "Recommendation: review doctor output for high-severity checks first, then medium recommendations." ;;
    "Maintenance Full") info "Recommendation: prioritize failed maintenance checks with highest operational blast radius." ;;
    "Security Scan (offline SARIF)") info "Recommendation: fail on high severity findings in branch protection for production branches." ;;
    "Security Triage (baseline-aware)") info "Recommendation: keep baseline current to prevent warning fatigue and improve signal quality." ;;
    "Control Plane Ops (CI profile)") info "Recommendation: track ops profile drift in PR comments to maintain consistency across repos." ;;
    "Evidence Pack") info "Recommendation: attach evidence bundle to release candidates for audit-readiness." ;;
    "Premium Gate Engine") info "Recommendation: use premium-summary.json in PR comments to guide remediation priorities." ;;
  esac
  info "Real-time: '$title' completed in ${elapsed}s"
}

preflight() {
  section "Preflight"
  local missing=0
  for cmd in bash python3 tee; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      warn "Missing required command: $cmd"
      missing=1
    fi
  done
  if (( missing != 0 )); then
    echo "ERROR: preflight failed" >&2
    exit 1
  fi
  pass "Preflight"
}

record_result() {
  local id="$1" head="$2" title="$3" cmd="$4" rc="$5" elapsed="$6" status="$7" log="$8" blocking="$9" reason="${10}"
  python3 - "$STEP_RESULTS_NDJSON" "$id" "$head" "$title" "$cmd" "$rc" "$elapsed" "$status" "$log" "$blocking" "$reason" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
entry = {
    "id": sys.argv[2],
    "head": sys.argv[3],
    "title": sys.argv[4],
    "cmd": sys.argv[5],
    "rc": int(sys.argv[6]),
    "elapsed_s": int(sys.argv[7]),
    "status": sys.argv[8],
    "log": sys.argv[9],
    "blocking": sys.argv[10] == "1",
    "reason": sys.argv[11],
}
path.write_text(path.read_text(encoding="utf-8") + json.dumps(entry, sort_keys=True) + "\n", encoding="utf-8")
PY
}

run_step() {
  local id="$1" head="$2" title="$3" cmd="$4" blocking="${5:-1}"
  local safe_title
  safe_title="$(echo "$title" | tr ' /()' '_____' | tr -cd '[:alnum:]_.-')"
  local step_log="$OUT_DIR/premium-gate.${safe_title}.log"
  section "[$head] $title"
  info "cmd: $cmd"
  local started ended elapsed rc status reason
  started="$(date +%s)"
  set +e
  bash -lc "$cmd" 2>&1 | tee "$step_log"
  rc=${PIPESTATUS[0]}
  set -e
  ended="$(date +%s)"
  elapsed="$((ended - started))"
  reason=""
  if (( rc == 0 )); then
    status="passed"
    pass "$title"
    runtime_recommendation "$title" "$elapsed"
  else
    status="failed"
    reason="command failed (rc=$rc)"
    echo "ERROR: step failed: $title"
    warn "How to fix: run the same command locally, inspect logs under $OUT_DIR, and remediate before re-running premium-gate.sh."
  fi
  record_result "$id" "$head" "$title" "$cmd" "$rc" "$elapsed" "$status" "$step_log" "$blocking" "$reason"
  if (( rc != 0 && CONTINUE_ON_ERROR == 0 )); then
    exit "$rc"
  fi
  return 0
}

skip_step() {
  local id="$1" head="$2" title="$3" reason="$4" blocking="${5:-0}"
  section "[$head] $title"
  info "skip: $reason"
  record_result "$id" "$head" "$title" "" 0 0 "skipped" "" "$blocking" "$reason"
}

emit_step_index() {
  python3 - "$STEP_INDEX_JSON" <<'PY'
import json
import os
import sys
from pathlib import Path

step_file = Path(os.environ["STEP_RESULTS_NDJSON"])
head_order = [
    "Head-1 Foundation & Quality",
    "Head-2 Source Truth & Style",
    "Head-3 Operational Confidence",
    "Head-4 Security & Compliance",
    "Head-5 Intelligence Brain",
]
steps = []
if step_file.exists():
    for raw in step_file.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        steps.append(json.loads(raw))
summary = {
    "mode": os.environ["MODE"],
    "out_dir": os.environ["OUT_DIR"],
    "five_heads": head_order,
    "total_steps": len(steps),
    "failed_steps": [s["id"] for s in steps if s.get("status") == "failed"],
    "skipped_steps": [s["id"] for s in steps if s.get("status") == "skipped"],
    "steps": steps,
}
Path(sys.argv[1]).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"wrote step index: {sys.argv[1]}")
PY
}

emit_final_verdict() {
  local profile requested_profile notes metadata_json
  profile="adaptive"
  requested_profile="adaptive"
  case "$MODE" in
    fast)
      profile="quick"
      requested_profile="quick"
      notes="Honest smoke confidence lane. Passing here is not the merge truth."
      ;;
    full)
      profile="strict"
      requested_profile="strict"
      notes="Full premium verification lane. This wraps bash quality.sh verify as the truth path."
      ;;
    engine-only)
      profile="adaptive"
      requested_profile="adaptive"
      notes="Adaptive/planner scaffold lane that isolates premium engine evidence collection."
      ;;
  esac
  metadata_json="$(python3 - "$MODE" "$STEP_RESULTS_NDJSON" <<'PY'
import json
import sys
from pathlib import Path

rows = []
for raw in Path(sys.argv[2]).read_text(encoding="utf-8").splitlines():
    raw = raw.strip()
    if not raw:
        continue
    rows.append(json.loads(raw))
print(
    json.dumps(
        {
            "source": "premium-gate.sh",
            "mode": sys.argv[1],
            "checks_recorded": len(rows),
            "execution": {"mode": "sequential", "workers": 1},
        },
        sort_keys=True,
    )
)
PY
)"
  python3 -m sdetkit.checks render-ledger \
    --profile "$profile" \
    --requested-profile "$requested_profile" \
    --ledger "$STEP_RESULTS_NDJSON" \
    --repo-root "$ROOT_DIR" \
    --out-dir "$OUT_DIR" \
    --profile-notes "$notes" \
    --metadata-json "$metadata_json" \
    --format text \
    --json-output "$PREMIUM_VERDICT_JSON" \
    --markdown-output "$PREMIUM_SUMMARY_MD" \
    --fix-plan-output "$PREMIUM_FIX_PLAN_JSON" \
    --risk-summary-output "$PREMIUM_RISK_SUMMARY_JSON" \
    --evidence-output "$PREMIUM_EVIDENCE_ZIP"
}

run_plan() {
  if [[ "$MODE" == "engine-only" ]]; then
    info "Mode engine-only: skipping upstream steps and running Head-5 only."
    skip_step "quality" "Head-1 Foundation & Quality" "Quality (engine-only skip)" "engine-only mode skips upstream quality lanes" 0
    skip_step "doctor_json" "Head-3 Operational Confidence" "Doctor JSON" "engine-only mode skips upstream operational evidence" 0
    skip_step "security_scan" "Head-4 Security & Compliance" "Security Scan (offline SARIF)" "engine-only mode skips upstream security scan" 0
    return
  fi

  local quality_title quality_cmd
  if [[ "$MODE" == "full" ]]; then
    if [[ "${GITHUB_EVENT_NAME:-}" == "pull_request" ]]; then
      quality_title="Quality (premerge strict changed-files)"
      quality_cmd="bash quality.sh premerge"
    else
      quality_title="Quality (full verification)"
      quality_cmd="bash quality.sh verify"
    fi
  else
    quality_title="Quality (fast/smoke)"
    quality_cmd="bash quality.sh ci"
  fi

  run_step "quality" "Head-1 Foundation & Quality" "$quality_title" "$quality_cmd" 1

  if [[ "$MODE" == "full" ]]; then
    run_step "ruff_format" "Head-2 Source Truth & Style" "Ruff (format check)" "python3 -m ruff format --check ." 1
    run_step "ruff_lint" "Head-2 Source Truth & Style" "Ruff (lint)" "python3 -m ruff check ." 1
    run_step "ci" "Head-3 Operational Confidence" "CI" "bash ci.sh" 1
    run_step "doctor_ascii" "Head-3 Operational Confidence" "Doctor ASCII" "python3 -m sdetkit doctor --ascii" 0
    run_step "doctor_json" "Head-3 Operational Confidence" "Doctor JSON" "python3 -m sdetkit doctor --json --out '$OUT_DIR/doctor.json'" 0
    run_step "maintenance_full" "Head-3 Operational Confidence" "Maintenance Full" "python3 -m sdetkit maintenance --mode full --format json --out '$OUT_DIR/maintenance.json'" 0
    run_step "integration_topology" "Head-3 Operational Confidence" "Integration Topology Contract" "python3 -m sdetkit integration topology-check --profile '$TOPOLOGY_PROFILE' > '$OUT_DIR/integration-topology.json'" 0
    run_step "security_scan" "Head-4 Security & Compliance" "Security Scan (offline SARIF)" "python3 -m sdetkit security scan --fail-on none --format sarif --output '$OUT_DIR/security.sarif'" 1
    run_step "security_triage" "Head-4 Security & Compliance" "Security Triage (baseline-aware)" "python3 tools/triage.py --mode security --run-security --security-baseline tools/security.baseline.json --max-items 20 --tee '$OUT_DIR/security-check.json'" 0
    run_step "ops_ci" "Head-3 Operational Confidence" "Control Plane Ops (CI profile)" "python3 -m sdetkit ops run --profile ci --jobs '$OPS_JOBS'" 0
    run_step "evidence" "Head-4 Security & Compliance" "Evidence Pack" "python3 -m sdetkit evidence pack --output '$OUT_DIR/evidence.zip'" 0
  else
    skip_step "ruff_format" "Head-2 Source Truth & Style" "Ruff (format check)" "fast mode relies on quality.sh ci for smoke-level source checks" 0
    skip_step "ruff_lint" "Head-2 Source Truth & Style" "Ruff (lint)" "fast mode relies on quality.sh ci for smoke-level source checks" 0
    run_step "doctor_json" "Head-3 Operational Confidence" "Doctor JSON" "python3 -m sdetkit doctor --json --out '$OUT_DIR/doctor.json'" 0
    run_step "integration_topology" "Head-3 Operational Confidence" "Integration Topology Contract" "python3 -m sdetkit integration topology-check --profile '$TOPOLOGY_PROFILE' > '$OUT_DIR/integration-topology.json'" 0
    run_step "security_scan" "Head-4 Security & Compliance" "Security Scan (offline SARIF)" "python3 -m sdetkit security scan --fail-on none --format sarif --output '$OUT_DIR/security.sarif'" 0
    skip_step "maintenance_full" "Head-3 Operational Confidence" "Maintenance Full" "fast mode omits the slower full maintenance lane" 0
    skip_step "evidence" "Head-4 Security & Compliance" "Evidence Pack" "fast mode omits release-grade evidence packaging" 0
  fi
}

run_engine() {
  section "Real-time warnings and recommendations summary"
  local engine_cmd
  engine_cmd="python3 -m sdetkit.premium_gate_engine --out-dir '$OUT_DIR' --double-check --min-score '$ENGINE_MIN_SCORE' --auto-fix --fix-root '$ROOT_DIR' --learn-db --learn-commit --db-path '$OUT_DIR/premium-insights.db' --format markdown --json-output '$OUT_DIR/premium-summary.json' --plan-output '$OUT_DIR/premium-remediation-plan.json'"
  if [[ -f "$SCRIPT_CATALOG" ]]; then
    engine_cmd+=" --script-catalog '$SCRIPT_CATALOG'"
  fi
  if [[ "$AUTO_RUN_SCRIPTS" == "1" ]]; then
    engine_cmd+=" --auto-run-scripts"
  fi
  run_step "premium_engine" "Head-5 Intelligence Brain" "Premium Gate Engine" "$engine_cmd" 0
}

final_report() {
  emit_step_index
  emit_final_verdict
  section "Premium Gate Final Report"
  python3 - "$STEP_RESULTS_NDJSON" <<'PY'
import json
import sys
from pathlib import Path

rows = []
for raw in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    raw = raw.strip()
    if not raw:
        continue
    rows.append(json.loads(raw))
failed = [r for r in rows if r.get("status") == "failed"]
skipped = [r for r in rows if r.get("status") == "skipped"]
print(f"steps: {len(rows)} | failed: {len(failed)} | skipped: {len(skipped)}")
if failed:
    print("failed step details:")
    for row in failed:
        print(f"- {row['head']} :: {row['title']} (rc={row['rc']})")
        print(f"  log: {row['log']}")
else:
    print("failed step details: none")
if skipped:
    print("skipped step details:")
    for row in skipped:
        print(f"- {row['head']} :: {row['title']} -> {row['reason']}")
print("next action: inspect logs and .sdetkit/out/premium-summary.json for prioritized remediation.")
PY

  if [[ -f "$OUT_DIR/premium-summary.json" ]]; then
    info "Engine JSON: $OUT_DIR/premium-summary.json"
  fi
  if [[ -f "$OUT_DIR/premium-remediation-plan.json" ]]; then
    info "Remediation plan: $OUT_DIR/premium-remediation-plan.json"
  fi
  info "Step index: $STEP_INDEX_JSON"
  info "Step run ledger: $STEP_RESULTS_NDJSON"
  info "Verdict JSON: $PREMIUM_VERDICT_JSON"
  info "Summary MD: $PREMIUM_SUMMARY_MD"
  info "Fix plan JSON: $PREMIUM_FIX_PLAN_JSON"
  info "Risk summary JSON: $PREMIUM_RISK_SUMMARY_JSON"
  info "Evidence ZIP: $PREMIUM_EVIDENCE_ZIP"
}

export MODE OUT_DIR STEP_RESULTS_NDJSON TOPOLOGY_PROFILE

preflight
run_plan
run_engine
final_report

echo "Premium gate passed. Artifacts: $OUT_DIR/doctor.json, $OUT_DIR/maintenance.json, $OUT_DIR/integration-topology.json, $OUT_DIR/security.sarif, $OUT_DIR/security-check.json, $OUT_DIR/premium-summary.json, $OUT_DIR/premium-remediation-plan.json, $PREMIUM_VERDICT_JSON, $PREMIUM_SUMMARY_MD, $PREMIUM_FIX_PLAN_JSON, $PREMIUM_RISK_SUMMARY_JSON, $PREMIUM_EVIDENCE_ZIP, $OUT_DIR/evidence.zip"
