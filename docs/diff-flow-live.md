# 🔄 DevS69 Diff-to-Decision — Live Detail View

This page is the dedicated **full Diff-to-Decision view**.

[![DevS69 Diff-to-Decision](assets/devs69-card-diff-flow.svg)](assets/devs69-card-diff-flow.svg){ target=_blank }

## Decision flow (full detail)

| Stage | Command | Artifact |
|---|---|---|
| Validate | `python -m pytest -q` | Test pass/fail signal |
| Audit | `python -m sdetkit repo audit --format markdown` | Quality findings |
| Secure | `python -m sdetkit security report --format sarif --output build/security.sarif` | SARIF output |
| Publish evidence | `python -m sdetkit proof --execute --strict --format markdown --output docs/artifacts/day3-proof-sample.md` | Shareable proof pack |
| Decide | `python -m sdetkit release-narrative --format markdown --output docs/artifacts/day20-release-narrative-sample.md` | Release decision narrative |

## Live + auto-updated signals

- ![CI](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/ci.yml/badge.svg)
- ![Mutation Tests](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/mutation-tests.yml/badge.svg)
- ![Security](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/security.yml/badge.svg)
- ![Last commit](https://img.shields.io/github/last-commit/sherif69-sa/DevS69-sdetkit)

## Related links

- [Open docs portal home](https://sherif69-sa.github.io/DevS69-sdetkit/)
- [Open HUD showcase index](hud-showcase.md)
