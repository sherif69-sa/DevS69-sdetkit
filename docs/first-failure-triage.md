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
| `python -m sdetkit doctor --format json --out build/doctor.json` | `next_action` plus `quality.failed_check_ids` in `build/doctor.json` | The first failing check and its `next_command` | Rerun `python -m sdetkit doctor --format json --out build/doctor.json` |

## When to use each command

- **Use `gate fast`** for first-line triage and day-to-day PR confidence.
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


## Checking a different repository

For Python check failures, `gate fast --root /path/to/project` keeps that root
and the check's interpreter in its focused `next_command`. You can copy the
command from the report without first changing your current directory or
activating a different environment. Paths with spaces are shell-quoted. Parametrized pytest cases keep their full
case ID, including spaces and brackets, so the follow-up selects the same case.

Run a disposable example on a POSIX shell with SDETKit and pytest installed:

```bash
python examples/gate/replay_external_failure.py
```

It creates an intentionally failing test in a temporary repository, runs the
gate from outside it, and executes the reported follow-up from another directory.
Success means the follow-up reproduces that same assertion failure, not a
missing-file or missing-interpreter error. The example removes its files on exit.
