# Day 2 demo path (target: ~60 seconds)

| Step | Command | Expected output snippets | Outcome |
|---|---|---|---|
| Health check | `python -m sdetkit doctor --format text` | `Doctor score:`<br>`Recommendations:` | Confirms repository hygiene and points to the highest-leverage fixes first. |
| Repository audit | `python -m sdetkit repo audit --format markdown` | `# Repo audit`<br>`## Findings` | Surfaces policy, CI, and governance gaps in a report-ready format. |
| Security baseline | `python -m sdetkit security --format markdown` | `# Security suite`<br>`## Checks` | Produces a security-focused snapshot that can be attached to release reviews. |

Related docs: [README quick start](../README.md#quick-start), [repo audit](repo-audit.md).
