# Adopt SDETKit in your repository

This page is for teams using SDETKit **outside this repository**.

It gives you a safe, copy-paste path from first run to stricter CI enforcement.

## What to install

Until public package release is completed, install from GitHub:

```bash
python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"
```

For CI and local development parity:

```bash
python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git#egg=sdetkit[dev,test]"
```

## Start small: local quick confidence

Run this first in your own repository root:

```bash
python -m sdetkit gate fast
```

This is a **signal-producing gate**, not a guaranteed-green onboarding command.

- Exit code `0`: your current repo state passes the fast checks.
- Non-zero exit code: one or more checks failed (for example lint/tests/type checks), which is expected if your repo is not yet aligned with the gate.

Why this is the right first command:

- Fast pass/fail signal with deterministic output.
- Minimal integration overhead.
- Good confidence before adding stricter gates.

If it fails, treat the output as your integration backlog: fix the first failing check, then rerun.

If you want a machine-readable artifact immediately:

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
```

## If a command fails on first adoption

Before changing your pipeline, check the focused troubleshooting matrix:

- [Adoption troubleshooting](adoption-troubleshooting.md)
- Covers common `gate fast`, `security enforce`, and `gate release` failures.
- Helps decide whether to fix quality debt now, tune a threshold temporarily, or stay on a lighter command.

## Add a lightweight CI gate (copy/paste)

Use this minimal GitHub Actions workflow in your repository.

```yaml
name: sdetkit-fast-gate

on:
  pull_request:
  push:
    branches: [main]

jobs:
  fast-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install SDETKit
        run: python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"
      - name: Run fast gate
        run: python -m sdetkit gate fast
```

## Graduate to stricter release gating

After fast gate is stable in your repo, add stricter checks:

```bash
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0
python -m sdetkit gate release
```

Suggested rollout:

1. **Week 1**: local + CI `gate fast` only.
2. **Week 2**: add security budgets in CI (start with a non-zero `--max-info` if needed).
3. **Week 3+**: enforce `gate release` for release branches/tags.

## CI pattern: fast on PR, strict on release branches

```yaml
name: sdetkit-progressive-gating

on:
  pull_request:
  push:
    branches: [main, release/**]

jobs:
  sdetkit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit.git"
      - name: Always run fast gate
        run: python -m sdetkit gate fast
      - name: Strict release gate
        if: startsWith(github.ref, 'refs/heads/release/')
        run: |
          python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0
          python -m sdetkit gate release
```

## Command choices at a glance

- Run first: `python -m sdetkit gate fast`
- CI minimum: `python -m sdetkit gate fast`
- Strict path: `python -m sdetkit security enforce ...` + `python -m sdetkit gate release`
- Evidence artifact: `python -m sdetkit gate fast --format json --stable-json --out ...`

## Related docs

- [Adoption troubleshooting](adoption-troubleshooting.md)
- [Ready-to-use quickstart](ready-to-use.md)
- [Release-confidence examples](examples.md)
- [Production readiness command](production-readiness.md)
