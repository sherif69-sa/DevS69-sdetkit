# Workflow local equivalents

This file maps workflow governance findings to local operator commands.
It is intentionally review-first and does not authorize workflow mutation or permission reduction.

Baseline governance check for every workflow:

```bash
python -m sdetkit workflow-governance-report --root . --format text
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

## `.github/workflows/dependency-review.yml`

Local equivalent command:

```bash
python -m sdetkit workflow-governance-report --root . --format text
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

## `.github/workflows/release-candidate.yml`

Local equivalent command:

```bash
make release-preflight && python -m build
```
