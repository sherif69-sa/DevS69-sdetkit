# Day 2 demo path (target: ~60 seconds)

| Step | Command | Expected output snippets | Outcome |
|---|---|---|---|
| Health check | `python -m sdetkit doctor --format text` | `doctor score:`<br>`recommendations:` | Confirms repository hygiene and points to the highest-leverage fixes first. |
| Repository audit | `python -m sdetkit repo audit --format text` | `Repo audit:`<br>`Result:` | Surfaces policy, CI, and governance gaps in a report-ready format. |
| Security baseline | `python -m sdetkit security report --format text` | `security scan:`<br>`top findings:` | Produces a security-focused snapshot that can be attached to release reviews. |

## Execution results

| Step | Status | Exit code | Duration (s) | Missing snippets |
|---|---|---:|---:|---|
| Health check | pass | 0 | 0.624 | - |
| Repository audit | pass | 0 | 1.086 | - |
| Security baseline | pass | 0 | 1.909 | - |

## SLA summary

- Total duration: `3.619s`
- Target: `60.0s`
- Within target: `yes`

## Closeout hints

- Use --execute when recording a live Day 2 walkthrough so each step is validated.
- Use --format markdown --output docs/artifacts/day2-demo-closeout.md to save a shareable run artifact.
- If a snippet check fails, rerun a single command manually and compare output with the expected markers.

Related docs: [README quick start](../README.md#quick-start), [repo audit](repo-audit.md).
