| Role | First command | Next action |
|---|---|---|
| SDET / QA engineer | `sdetkit doctor --format markdown` | Run `sdetkit repo audit --format markdown` and triage the highest-signal findings. |
| Platform / DevOps engineer | `sdetkit repo audit --format markdown` | Wire checks into CI with `docs/github-action.md` and enforce deterministic gates. |
| Security / compliance lead | `sdetkit security --format markdown` | Apply policy controls from `docs/security.md` and `docs/policy-and-baselines.md`. |
| Engineering manager / tech lead | `sdetkit doctor --format markdown` | Standardize team workflows using `docs/automation-os.md` and `docs/repo-tour.md`. |

Quick start: [Repo audit quick start](../repo-audit.md#quick-start)
