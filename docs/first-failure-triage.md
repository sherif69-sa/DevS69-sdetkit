# First-failure triage (core release-confidence path)

Use this page right after your **first failed core run** (`gate fast`, `gate release`, or `doctor`).

Goal: recover quickly, fix the right thing first, and avoid guessing.

## 60-second decision path

1. Run (or open) `gate fast` output first and read the `next_action` card.
2. Fix the **first failed quality step** (`ruff` / `mypy` / `pytest`) before moving to stricter gates.
3. If the first failing line is still unclear, run `python -m sdetkit investigate failure`.
4. Run `gate release` after `gate fast` is stable.
5. Use `doctor --format json --out build/doctor.json` when release prerequisites are unclear.

## Saved CI log triage

When a GitHub Actions job already failed, save the failed step log to a local file and ask the advisory investigation command to summarize the real blocker:

```bash
python -m sdetkit investigate failure --log /tmp/failed-ci.log --format markdown
```

Use `--format json` when another tool needs the same report fields, or `--format text` for compact terminal output.

The report is advisory only. It identifies the parsed blocker, likely owner files, wrapper noise to ignore, and verification commands. It does not edit files, lower gates, commit, push, or merge anything.

Use it before patching when the loud final line is only a wrapper, such as a nonzero process exit after a pytest, mypy, MkDocs, coverage, or pre-commit failure.

## Fix-first matrix

| What failed? | Check first | Fix before moving on | Run next |
| --- | --- | --- | --- |
| `python -m sdetkit gate fast` | `next_action` plus `failed_steps` in terminal output or `build/gate-fast.json` | The first failing step category (usually `ruff`, `mypy`, or `pytest`) | Rerun `python -m sdetkit gate fast` |
| `python -m sdetkit investigate failure --log /tmp/failed-ci.log --format markdown` | `affected_file`, `first_failing_line`, and `local_repro_command` | Reproduce the first failure locally with the recommended proof command | Rerun `python -m sdetkit gate fast` |
| `python -m sdetkit gate release` | `next_action` plus `failed_steps` (commonly `doctor_release` or `gate_fast`) | Clear upstream failures in order; if `gate_fast` appears, fix that first | Run `python -m sdetkit doctor --format json --out build/doctor.json`, then rerun `gate release` |

## When to use each command

- **Use `gate fast`** for first-line triage and impact-to-impact PR confidence.
- **Use `investigate failure`** when a saved CI log or gate step log needs a first-failure diagnosis before patching.
- **Use `doctor`** when `gate release` fails and you need release-prerequisite detail.

## Minimal triage order (recommended)

1. `python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json`
2. Fix first failing quality step and rerun `python -m sdetkit gate fast`
3. `python -m sdetkit gate release --format json --out build/release-preflight.json`
4. `python -m sdetkit doctor --format json --out build/doctor.json`

If you need expanded playbooks after this compact pass, continue with:

- [Adoption troubleshooting](adoption-troubleshooting.md)
- [Remediation cookbook](remediation-cookbook.md)
