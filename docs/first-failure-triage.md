# First-failure triage (core release-confidence path)

Use this page right after your **first failed core run** (`gate fast`, `security enforce`, or `gate release`).

Goal: recover quickly, fix the right thing first, and avoid guessing.

## 60-second decision path

1. Run (or open) `gate fast` output first.
2. Fix the **first failed quality step** (`ruff` / `mypy` / `pytest`) before moving to stricter gates.
3. Run `security enforce` after `gate fast` is stable; tune only `--max-info` temporarily if needed.
4. Run `gate release` after fast gate + security posture are stable.
5. Use `doctor --release` when release prerequisites are unclear.

## Fix-first matrix

| What failed? | Check first | Fix before moving on | Run next |
| --- | --- | --- | --- |
| `python -m sdetkit gate fast` | `failed_steps` in terminal output or `build/gate-fast.json` | The first failing step category (usually `ruff`, `mypy`, or `pytest`) | Rerun `python -m sdetkit gate fast` |
| `python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0` | `ok`, `counts`, `exceeded`, `limits` in JSON output | Keep `--max-error 0 --max-warn 0`; if onboarding, set a temporary realistic `--max-info` baseline and plan ratcheting down | Rerun `security enforce`, then continue to `gate release` |
| `python -m sdetkit gate release` | `failed_steps` (commonly `doctor_release` or `gate_fast`) | Clear upstream failures in order; if `gate_fast` appears, fix that first | Run `python -m sdetkit doctor --release --format json`, then rerun `gate release` |

## When to use each command

- **Use `gate fast`** for first-line triage and day-to-day PR confidence.
- **Use `doctor --release`** when `gate release` fails and you need release-prerequisite detail.
- **Use `security enforce`** to evaluate policy budgets (`error`/`warn`/`info`) after quality checks are under control.

## Minimal triage order (recommended)

1. `python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json`
2. Fix first failing quality step and rerun `python -m sdetkit gate fast`
3. `python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0`
4. `python -m sdetkit gate release --format json --out build/release-preflight.json`

If you need expanded playbooks after this compact pass, continue with:

- [Adoption troubleshooting](adoption-troubleshooting.md)
- [Remediation cookbook](remediation-cookbook.md)
