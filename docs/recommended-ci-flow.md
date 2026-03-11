# Recommended CI flow for team adoption

This page is the **canonical CI rollout guide** for operationalizing SDETKit in GitHub Actions with minimal friction.

**Not this page:** first-time local users should start with [First run quickstart](ready-to-use.md); team onboarding should start with [Adoption](adoption.md).

For a compact reviewer/operator read path over CI artifacts, see [CI artifact walkthrough](ci-artifact-walkthrough.md).

It is intentionally small and derived from this repository's current CI/release patterns in:

- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `docs/adoption.md`

For tier and scope boundaries, use [integrations-and-extension-boundary.md](integrations-and-extension-boundary.md).

## Recommended shape

Use three stages:

1. **Pull requests (fast feedback):** block on `gate fast`; always upload fast diagnostics.
2. **`main` branch (stricter confidence):** keep fast gate, then run security thresholds + full quality/docs checks.
3. **Release tags (release-oriented):** run release preflight + build validation + wheel smoke before publish.

This gives teams quick PR signal, stronger merge confidence, and explicit release controls without forcing strict release checks on every feature branch.

## Minimal baseline workflow (GitHub Actions)

```yaml
name: sdetkit-recommended-baseline

on:
  pull_request:
  push:
    branches: [main]
    tags: ["v*.*.*"]

jobs:
  pr-and-main:
    if: github.ref_type != 'tag'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install project + CI extras
        run: python -m pip install -e .[dev,test,docs]

      # Fast PR-safe gate (also emits JSON when artifact-dir is set)
      - name: Fast gate
        run: bash ci.sh quick --skip-docs --artifact-dir build

      # Keep threshold evidence even when gate fails
      - name: Security diagnostics (non-blocking)
        if: always()
        continue-on-error: true
        run: python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0 --out build/security-enforce.json

      # Tighten only on main
      - name: Main branch stricter checks
        if: github.ref == 'refs/heads/main'
        env:
          COV_FAIL_UNDER: "95"
        run: |
          python -m pre_commit run -a
          bash quality.sh cov
          NO_MKDOCS_2_WARNING=1 python -m mkdocs build

      - name: Upload CI diagnostics
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: ci-gate-diagnostics
          path: |
            build/gate-fast.json
            build/security-enforce.json
          if-no-files-found: warn

  release:
    if: github.ref_type == 'tag'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install release tooling
        run: python -m pip install -r requirements-test.txt -r requirements-docs.txt -e .[packaging]
      - name: Release preflight + package validation
        run: |
          mkdir -p build
          python scripts/release_preflight.py --tag "${GITHUB_REF_NAME}" --format json --out build/release-preflight.json
          python scripts/check_release_tag_version.py "${GITHUB_REF_NAME}"
          python -m build
          python -m twine check dist/*
          python -m check_wheel_contents --ignore W009 dist/*.whl
          python -m pip install --force-reinstall dist/*.whl
          sdetkit --help
      - name: Upload release diagnostics
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: release-diagnostics
          path: build/release-preflight.json
          if-no-files-found: warn
```

## Stage-by-stage command recommendations

### Pull requests (fast feedback)

- `bash ci.sh quick --skip-docs --artifact-dir build`
- `python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0 --out build/security-enforce.json` (non-blocking diagnostics)

Why: fast and deterministic contributor signal, with triage-ready JSON artifacts.

### `main` branch (stricter checks)

Keep PR commands, then add:

- `python -m pre_commit run -a`
- `bash quality.sh cov`
- `NO_MKDOCS_2_WARNING=1 python -m mkdocs build`

Why: stronger confidence on integrated code without slowing every PR.

### Release-oriented workflow (tags)

- `python scripts/release_preflight.py --tag "${GITHUB_REF_NAME}" --format json --out build/release-preflight.json`
- `python scripts/check_release_tag_version.py "${GITHUB_REF_NAME}"`
- `python -m build`
- `python -m twine check dist/*`
- `python -m check_wheel_contents --ignore W009 dist/*.whl`
- `python -m pip install --force-reinstall dist/*.whl && sdetkit --help`

Why: explicit release metadata validation + package integrity + installability proof.

## Artifacts to preserve

For CI failure triage and release reviews, keep:

- `build/gate-fast.json` (fast lane failed step details)
- `build/security-enforce.json` (threshold counts/exceeded budgets)
- `build/release-preflight.json` (release metadata status)

Recommended upload names:

- `ci-gate-diagnostics`
- `release-diagnostics`

## Progressive adoption path

1. **Week 1:** PR-only `gate fast` with diagnostics upload.
2. **Week 2:** Add security threshold diagnostics, then enforce stricter thresholds once noise is reduced.
3. **Week 3+:** Apply stricter `main` checks (coverage/docs/pre-commit).
4. **Release maturity:** Add tag-triggered release preflight + package validation.

This sequencing avoids "all-at-once" CI pain while still moving toward deterministic release confidence.

## When checks fail

- **Fast gate failed:** open `build/gate-fast.json`; fix the first failing step before broad refactors.
- **Security threshold exceeded:** open `build/security-enforce.json`; either remediate findings or temporarily tune thresholds with an explicit follow-up issue.
- **Release preflight failed:** open `build/release-preflight.json`; fix tag/version metadata mismatch first.

For remediation playbooks, use:

- `docs/adoption-troubleshooting.md`
- `docs/remediation-cookbook.md`

## Keep it lighter for smaller repositories

If your repo is small or early-stage, keep only:

- PR: `python -m sdetkit gate fast`
- Optional JSON artifact: `python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json`

Delay coverage/doc/release packaging jobs until the fast lane is stable and trusted by the team.
