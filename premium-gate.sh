#!/usr/bin/env bash
set -euo pipefail

mkdir -p .sdetkit/out
python -m sdetkit release gate fast --format json > .sdetkit/out/premium-release-gate-fast.json || true
python -m sdetkit repo check --format json --out .sdetkit/out/premium-repo-audit.json --force
python -m sdetkit doctor --format json --out .sdetkit/out/premium-doctor.json || true

echo "premium gate checks completed"
