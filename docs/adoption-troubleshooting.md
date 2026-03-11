# Adoption troubleshooting (external repositories)

Use this page when you are integrating SDETKit into **your own repo** and a command fails.

The goal is to decide quickly:

- Is this failure expected during onboarding?
- Should you fix code issues now, loosen policy temporarily, or run a lighter command?
- What is the next sensible adoption step?

## Quick command intent map

| Command | Primary purpose | Typical onboarding outcome |
| --- | --- | --- |
| `python -m sdetkit gate fast` | Fast repo-health signal (doctor + templates + lint + type + tests) | Often fails at first; use failures as adoption backlog |
| `python -m sdetkit security enforce ...` | Enforce security finding budgets | Strict limits commonly fail until thresholds are tuned |
| `python -m sdetkit gate release` | Stricter release go/no-go gate | Usually fails until `gate fast` and policy prerequisites are stable |

## Copy-paste remediation playbooks

If you already know what failed and just want the exact next commands, use:

- [Remediation cookbook](remediation-cookbook.md)

If you are diagnosing a failed GitHub Actions run, download CI artifacts first:

- `ci-gate-diagnostics` (contains `build/gate-fast.json` and `build/security-enforce.json`)
- `release-diagnostics` (contains `build/release-preflight.json`)

These files make `failed_steps` and threshold outcomes inspectable without scrolling long logs.

## Troubleshooting matrix

| What you see | Usually means | What to do next | Stay lightweight vs tighten later |
| --- | --- | --- | --- |
| `gate fast: FAIL` with a failed step like `ruff`, `mypy`, or `pytest` | SDETKit is working and surfaced real quality debt in your repo | Run the failing tool directly, fix one issue class, rerun `gate fast` | Keep using `gate fast` on PRs until it is consistently green |
| `security enforce` exits non-zero with `"ok": false` and `exceeded` for `info`/`warn`/`error` | Your current findings are above configured budgets | Keep `--max-error 0 --max-warn 0`, raise `--max-info` to current baseline, then ratchet down over time | Start with realistic budgets, then tighten per release cycle |
| `gate release: FAIL` with failed steps such as `doctor_release` and/or `gate_fast` | Release prerequisites are not yet satisfied (for example clean-tree/release checks or fast-gate failures) | Read `failed_steps`, run the failed checks directly, and clear them in order | Keep release gate for release branches/tags until fast gate and release prerequisites are consistently green |
| `bash scripts/ready_to_use.sh quick` prints CI lane issues but exits `0` | Quick mode is onboarding-friendly and does not block on CI quick lane failure | Treat printed failing checks as backlog; use direct commands in your repo for enforcement | Use quick mode for first-day setup, not as merge policy |

## Grounded examples from this repository

These are representative outputs from real runs in this repo.

### 1) `gate fast` failed on lint (`ruff`)

```text
gate: problems found
gate fast: FAIL
[OK] doctor (...) rc=0
[OK] ci_templates (...) rc=0
[FAIL] ruff (...) rc=1
[OK] mypy (...) rc=0
[OK] pytest (...) rc=0
failed_steps:
- ruff
```

Next step:

```bash
ruff check .
```

### 2) strict security budget failed, relaxed budget passed

```bash
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0
```

```json
{"counts":{"error":0,"info":131,"total":131,"warn":0},"ok":false,"exceeded":[{"metric":"info","count":131,"limit":0}]}
```

```bash
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 200
```

```json
{"counts":{"error":0,"info":131,"total":131,"warn":0},"ok":true,"exceeded":[]}
```

### 3) `gate release` failed on release prerequisites

```text
gate: problems found
gate release: FAIL
[FAIL] doctor_release rc=2
[OK] playbooks_validate rc=0
[FAIL] gate_fast rc=2
failed_steps:
- doctor_release
- gate_fast
```

## Progressive adoption decisions

1. **First integration:** run `gate fast` locally and in PR CI.
2. **If it fails:** fix the first failing step category (lint/type/tests), not everything at once.
3. **Then add security budgets:** keep errors/warnings strict, set `--max-info` to a temporary baseline.
4. **Finally enforce release gate:** apply on release branches/tags once fast gate is reliable.

If you want the full copy-paste integration workflow, go back to [adoption.md](adoption.md).
