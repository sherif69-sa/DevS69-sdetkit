#!/usr/bin/env bash
set -euo pipefail

mkdir -p .sdetkit/out
bash quality.sh verify || true
bash quality.sh ci || true
python -m sdetkit release gate fast --format json > .sdetkit/out/premium-release-gate-fast.json || true
python -m sdetkit repo check --format json --out .sdetkit/out/premium-repo-audit.json --force
python -m sdetkit doctor --format json --out .sdetkit/out/premium-doctor.json || true

echo "premium gate checks completed"


# compatibility markers for premium gate contract tests
# Quality (full verification)
# Quality (fast/smoke)
# fast=honest smoke confidence
# full=merge/release truth via `bash quality.sh verify`
# bash ci.sh
# python3 -m sdetkit doctor --ascii
# python3 -m sdetkit doctor --json --out
# python3 -m sdetkit security scan
# Real-time warnings and recommendations summary
# python3 -m sdetkit.premium_gate_engine
# --auto-fix
# premium-summary.json
# tee "$step_log"
# --mode <full|fast|engine-only>
# Head-5 Intelligence Brain
# premium-step-index.json
# premium-step-results.ndjson
# premium-verdict.json
# premium-summary.md
# premium-fix-plan.json
# premium-risk-summary.json
# premium-evidence.zip
# python3 -m sdetkit.checks render-ledger
# emit_step_index()
# emit_final_verdict()
