| Role | First command | Next action |
|---|---|---|
| SDET / QA engineer | `sdetkit doctor --format markdown` | Run `sdetkit repo audit --format markdown` and triage the highest-signal findings. |
| Platform / DevOps engineer | `sdetkit repo audit --format markdown` | Wire checks into CI with `docs/github-action.md` and enforce deterministic gates. |
| Security / compliance lead | `sdetkit security --format markdown` | Apply policy controls from `docs/security.md` and `docs/policy-and-baselines.md`. |
| Engineering manager / tech lead | `sdetkit doctor --format markdown` | Standardize team workflows using `docs/automation-os.md` and `docs/repo-tour.md`. |

## Day 5 platform onboarding snippets

### Linux (bash)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-test.txt -e .
python -m sdetkit doctor --format text
```

### macOS (zsh/bash)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-test.txt -e .
python -m sdetkit doctor --format text
```

### Windows (PowerShell)

```bash
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-test.txt -e .
python -m sdetkit doctor --format text
```

Quick start: [README quick start](../../README.md#quick-start)
