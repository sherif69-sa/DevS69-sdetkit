# Recommended CI flow for team adoption (canonical)

This page defines one canonical baseline CI path for deterministic release confidence.

First-time local users should start with [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md) and [First run quickstart](ready-to-use.md).

Canonical artifact decoding is in [CI artifact walkthrough](ci-artifact-walkthrough.md).

## Canonical baseline shape

Use three stages:

1. **Pull requests:** run fast gate; always upload diagnostics.
2. **`main` branch:** keep fast gate + security diagnostics; add stricter quality/docs checks.
3. **Release tags:** run release preflight + package validation + install smoke.

This is derived from current workflows:
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`

## Canonical baseline workflow (GitHub Actions)

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

      - name: Fast gate
        run: bash ci.sh quick --skip-docs --artifact-dir build

      - name: Security diagnostics (non-blocking)
        if: always()
        continue-on-error: true
        run: python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0 --out build/security-enforce.json

      - name: Main branch stricter checks
        if: github.ref == 'refs/heads/main'
        env:
          COV_FAIL_UNDER: "95"
        run: |
          python -m pre_commit run -a
          bash quality.sh registry
          bash quality.sh cov
          NO_MKDOCS_2_WARNING=1 python -m mkdocs build

      - name: Upload CI diagnostics
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: ci-gate-diagnostics-py3.12
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

## Artifacts to preserve

- `build/release-preflight.json`
- `build/gate-fast.json`
- `build/security-enforce.json`

Current workflow upload names in this repo:
- `ci-gate-diagnostics-py3.11`
- `ci-gate-diagnostics-py3.12`
- `release-diagnostics`

## When checks fail

- Fast gate failed: open `build/gate-fast.json`; fix first failed step.
- Security threshold exceeded: open `build/security-enforce.json`; remediate or tune thresholds with follow-up.
- Release preflight failed: open `build/release-preflight.json`; fix tag/version/changelog mismatch first.

## Secondary appendix: optional maintenance automation

This repo also has optional maintenance workflows (GHAS, dependency radar, docs experience, runtime watchlist, etc.).
These are secondary and should not replace the canonical CI merge/release evidence path above.
