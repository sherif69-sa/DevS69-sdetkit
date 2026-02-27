# 🕹️ DevS69 Command HUD — Live Detail View

This page is the dedicated **full Command HUD view**.

[![DevS69 Command HUD](assets/devs69-card-hud.svg)](assets/devs69-card-hud.svg){ target=_blank }

## Command lanes (full detail)

| HUD lane | Command | Expected output | Why it matters |
|---|---|---|---|
| Health baseline | `python -m sdetkit doctor --format markdown` | Health score + recommended next actions | Fast system readiness check |
| Governance checks | `python -m sdetkit repo audit --format markdown` | Policy and hygiene findings | Keeps repo quality enforceable |
| Security hardening | `python -m sdetkit security scan --format text` | Vulnerability/risk overview | Reduces release risk |
| Workflow orchestration | `python -m sdetkit agent run 'action repo.audit {"profile":"default"}' --approve` | Deterministic automation execution | Scales repeatable operations |

## Live + auto-updated signals

These pull directly from GitHub and update whenever CI/workflows or the default branch changes.

- ![Pages](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/pages.yml/badge.svg)
- ![CI](https://github.com/sherif69-sa/DevS69-sdetkit/actions/workflows/ci.yml/badge.svg)
- ![Last commit](https://img.shields.io/github/last-commit/sherif69-sa/DevS69-sdetkit)
- ![Latest release](https://img.shields.io/github/v/release/sherif69-sa/DevS69-sdetkit?sort=semver)

## Related links

- [Open docs portal home](https://sherif69-sa.github.io/DevS69-sdetkit/)
- [Open HUD showcase index](hud-showcase.md)
