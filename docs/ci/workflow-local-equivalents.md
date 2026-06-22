# Workflow local equivalents

This file maps workflow governance findings to local operator commands.
It is intentionally review-first and does not authorize workflow mutation or permission reduction.

Baseline governance check for every workflow:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

## `.github/workflows/adapter-smoke-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
python -m pip install -c constraints-ci.txt -e .[test]
|
python -m sdetkit agent templates run adapter-smoke-worker --output-dir .sdetkit/agent/template-runs/adapter-smoke-worker > build/adapter-smoke-worker-run.json
python - <<'PY'
```

## `.github/workflows/adaptive-ops-weekly.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m venv .venv
python -m pip install -c constraints-ci.txt -e .[dev,test,docs]
make adaptive-ops-bundle DATE_TAG="$DATE_TAG" ADAPTIVE_SCENARIO="$ADAPTIVE_SCENARIO"
```

## `.github/workflows/adaptive-sentinel-monitor.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt -r requirements-test.txt -e .
python - <<'PY' >> "$GITHUB_STEP_SUMMARY"
```

## `.github/workflows/adoption-real-repo-canonical.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
python -m pip install -c constraints-ci.txt -e .
python scripts/regenerate_real_repo_adoption_goldens.py --check
|
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor --format json --out build/doctor.json
python ../../../scripts/real_repo_adoption_projection.py \
```

## `.github/workflows/contributor-onboarding-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

## `.github/workflows/dependency-audit.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt pip-audit==2.10.0
python -m pip install -c constraints-ci.txt -e .
python .github/scripts/check_pip_audit_baseline.py
```

## `.github/workflows/dependency-auto-merge.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

## `.github/workflows/dependency-radar-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
python -m pip install -c constraints-ci.txt -e .
|
python -m sdetkit intelligence upgrade-audit --format json --used-in-repo-only --top 10 > build/dependency-radar.json
python -m sdetkit intelligence upgrade-audit --impact-area runtime-core --repo-usage-tier hot-path --format md > build/runtime-fast-follow.md
python - <<'PY'
```

## `.github/workflows/dependency-review.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

## `.github/workflows/docs-experience-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python - <<'PY'
```

## `.github/workflows/docs-link-check.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

## `.github/workflows/enforce-branch-protection.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
python -m pip install -c constraints-ci.txt -e .
|
python tools/enforce_branch_protection.py \
```

## `.github/workflows/enterprise-gate.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt -U pip
python -m pip install -c constraints-ci.txt -e .
sdetkit doctor --all --format json --out build/doctor-enterprise.json || true
python - <<'PY'
sdetkit repo check . --profile enterprise --format json --out sdet_check.json --force || rc=$?
```

## `.github/workflows/first-proof-artifact-publish.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt --upgrade pip
python -m pip install -c constraints-ci.txt -e .
make first-proof-verify-local
```

## `.github/workflows/first-proof.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt --upgrade pip
python -m pip install -c constraints-ci.txt -r requirements-test.txt -e .
make first-proof-verify
python - <<'PY'
```

## `.github/workflows/ghas-alert-sla-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

## `.github/workflows/ghas-campaign-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

## `.github/workflows/ghas-codeql-hotspots-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

## `.github/workflows/ghas-metrics-export-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

## `.github/workflows/ghas-review-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

## `.github/workflows/impact-release-control.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt -e .
python -m pip install -c constraints-ci.txt -r requirements-test.txt
python scripts/impact_policy_validate.py \
python scripts/impact_workflow_run.py \
python scripts/impact_trend_alert.py \
python scripts/impact_step1_scorecard.py \
python scripts/impact_step_scorecards.py \
```

## `.github/workflows/integration-topology-radar-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
python -m pip install -c constraints-ci.txt -e .[test]
|
python -m sdetkit agent templates run integration-topology-worker --output-dir .sdetkit/agent/template-runs/integration-topology-worker > build/integration-topology-worker-run.json
python - <<'PY'
```

## `.github/workflows/kpi-weekly.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
python -m pip install -c constraints-ci.txt -e .[dev,test]
|
python -m ruff check src tests --output-format json > build/ruff-report.json || true
python -m mypy src/sdetkit --hide-error-context --no-color-output --no-error-summary > build/mypy-report.txt || true
bash -lc "$CMD"
python - <<'PY'
python -m sdetkit kpi-report \
```

## `.github/workflows/legacy-required-status-bridge.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

## `.github/workflows/maintenance-autopilot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt -e .[dev,test]
python - <<'PY'
```

## `.github/workflows/maintenance-issue-command-center.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
python -m pip install -c constraints-ci.txt -e .
|
```

## `.github/workflows/maintenance-on-demand.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt -e .[dev,test]
bash scripts/maintenance_ci.sh "${{ inputs.mode }}" "${{ inputs.fix && 'true' || 'false' }}" artifacts/maintenance
python -m sdetkit.github_actions_annotation_hygiene_report \
python -m sdetkit.maintenance_priority_rollup \
python -m sdetkit.maintenance_policy_decisions \
python -m sdetkit.maintenance_policy_memory_context \
python -m sdetkit.maintenance_recommendations \
```

## `.github/workflows/operational-readiness-governance-contract.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m venv .venv
python -m pip install -c constraints-ci.txt -e .
make governance-contract-check
python - <<'PYCODE'
```

## `.github/workflows/osv-scanner.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
./
```

## `.github/workflows/pages.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt -r requirements-docs.txt -e .
python scripts/check_public_surface_alignment.py
NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict
```

## `.github/workflows/platform-readiness-quality-contract.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt --upgrade pip
python -m pip install -c constraints-ci.txt -r requirements-test.txt -r requirements-docs.txt -e .
python scripts/seed_quality_baseline_summary_fixture.py --summary build/baseline-baseline/baseline-baseline-summary.json
make quality-contract-run
```

## `.github/workflows/pr-quality-comment.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt -r requirements-test.txt -r requirements-docs.txt -e .
bash quality.sh cov 2>&1 | tee build/pr-quality/failure-intelligence/quality.log
gh api graphql \
gh api \
python - <<'PY'
bash build/pr-quality/check-logs/download-failed-check-logs.sh || true
gh run download "$trusted_history_run_id" \
```

## `.github/workflows/pre-commit-autoupdate.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt pre-commit
pre-commit autoupdate
```

## `.github/workflows/premium-gate.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt --upgrade pip
python -m pip install -c constraints-ci.txt -e '.[dev,test,docs]'
bash premium-gate.sh
```

## `.github/workflows/quality.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt -e .[dev,test,docs]
python -m sdetkit.doctor --ascii
python -m pre_commit run -a
bash quality.sh registry
bash quality.sh cov
```

## `.github/workflows/release-readiness-radar-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
python -m pip install -c constraints-ci.txt -e .[test]
|
python -m sdetkit doctor --format json > build/release-readiness-doctor.json || true
python -m sdetkit maintenance --include-check github_automation_check --format json > build/release-readiness-maintenance.json || true
python - <<'PY'
```

## `.github/workflows/release.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python scripts/release_preflight.py --tag "${{ steps.resolved.outputs.tag }}" --format json --out build/release-preflight.json
python scripts/check_release_tag_version.py "${{ steps.resolved.outputs.tag }}"
python -m pip install -c constraints-ci.txt -r requirements-test.txt -r requirements-docs.txt -e .[packaging]
bash quality.sh cov
python -m build
python -m twine check dist/*
python -m check_wheel_contents --ignore W009 dist/*.whl
```

## `.github/workflows/repo-audit.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

## `.github/workflows/repo-memory-history.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt -r requirements-test.txt -e .
python - <<'PY'
gh api --paginate \
gh run download "$prior_run_id" \
gh api \
```

## `.github/workflows/repo-optimization-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt --upgrade pip
python -m pip install -c constraints-ci.txt -e .
python -m sdetkit kits optimize "repo optimization control loop" --format json --limit 3 > build/repo-optimization.json
python - <<'PY'
```

## `.github/workflows/runtime-watchlist-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
python -m pip install -c constraints-ci.txt -e .[test]
|
python -m sdetkit agent templates run runtime-watchlist-worker --output-dir .sdetkit/agent/template-runs/runtime-watchlist-worker > build/runtime-watchlist-worker-run.json
python - <<'PY'
```

## `.github/workflows/sbom.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt -r requirements-test.txt -r requirements-docs.txt -e .
python -m pip install -c constraints-ci.txt cyclonedx-bom==7.3.0
```

## `.github/workflows/secret-protection-review-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

## `.github/workflows/security-configuration-audit-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

## `.github/workflows/security-maintenance-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
```

## `.github/workflows/security.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

## `.github/workflows/versioning.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
```

## `.github/workflows/weekly-maintenance.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python -m pip install -c constraints-ci.txt -e .[dev,test]
bash scripts/maintenance_ci.sh full false artifacts/maintenance
python - <<'PY'
bash scripts/maintenance_ci.sh full true artifacts/maintenance
```

## `.github/workflows/worker-alignment-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
python -m pip install -c constraints-ci.txt -e .[dev,test,docs]
|
python -m sdetkit agent templates run adapter-smoke-worker --output-dir .sdetkit/agent/template-runs/adapter-smoke-worker > build/adapter-smoke-worker-run.json
python -m sdetkit agent templates run dependency-radar-worker --output-dir .sdetkit/agent/template-runs/dependency-radar-worker > build/dependency-radar-worker-run.json
python -m sdetkit agent templates run docs-search-radar --output-dir .sdetkit/agent/template-runs/docs-search-radar > build/docs-search-radar-run.json
python -m sdetkit agent templates run integration-topology-worker --output-dir .sdetkit/agent/template-runs/integration-topology-worker > build/integration-topology-worker-run.json
python -m sdetkit agent templates run release-readiness-worker --output-dir .sdetkit/agent/template-runs/release-readiness-worker > build/release-readiness-worker-run.json
python -m sdetkit agent templates run runtime-watchlist-worker --output-dir .sdetkit/agent/template-runs/runtime-watchlist-worker > build/runtime-watchlist-worker-run.json
```

## `.github/workflows/workflow-governance-bot.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
```

Workflow command hints extracted from the YAML for operator review:

```bash
|
python - <<'PY'
```

## Workflow contracts

```bash
python scripts/check_workflow_contracts.py \
  --root . \
  --topology-contract docs/contracts/workflow-topology.v1.json \
  --required-checks-contract docs/contracts/required-checks.v1.json \
  --out-json build/workflow-contracts/report.json \
  --out-md build/workflow-contracts/report.md
```

For an authenticated live required-context comparison:

```bash
gh api repos/sherif69-sa/DevS69-sdetkit/branches/main/protection/required_status_checks/contexts \
  > /tmp/devs69-required-contexts.json

python scripts/check_workflow_contracts.py \
  --root . \
  --live-required-contexts-json /tmp/devs69-required-contexts.json
```

The checker is reporting-only. It does not change branch protection, workflows, permissions, or merge state.

## PR Quality trusted publisher

The publisher has no repository-code local equivalent because it is a GitHub control-plane action.
Validate the boundary locally with:

```bash
python -m pytest -q \
  tests/test_pr_quality_comment_observability_workflow.py \
  tests/test_pr_quality_publisher_trust_boundary.py \
  -o addopts=
```

The evidence workflow remains locally reproducible through the existing PR Quality commands. The
publisher consumes only the verified handoff artifact and uses the GitHub API to update the PR
comment.
