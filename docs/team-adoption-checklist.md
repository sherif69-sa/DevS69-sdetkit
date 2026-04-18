# Team adoption checklist

Use this as a short rollout checklist for first-time team adoption.

## Runtime baseline

- [ ] Python 3.11+ confirmed on developer machines and CI runners
- [ ] Team can create and activate isolated Python environments

## Install approach

- [ ] Isolated install mode chosen (`venv` for project-local, or `pipx` for app-style)
- [ ] Team avoids bare system `pip install` on Ubuntu/WSL (externally-managed risk)
- [ ] Install commands are documented in team onboarding notes

## First-run proof

- [ ] Canonical commands run locally in a clean repository checkout
- [ ] `build/release-preflight.json` is generated
- [ ] `build/gate-fast.json` is generated
- [ ] `python -m sdetkit doctor` completes

## CI adoption

- [ ] CI path chosen (start with one lane, then expand)
- [ ] CI stores JSON artifacts for review
- [ ] CI output matches local command path as closely as possible

## Artifact review expectations

- [ ] Review order is agreed: `release-preflight.json` → `gate-fast.json` → logs
- [ ] Team has a clear owner for artifact triage on failures
- [ ] PR/release decisions reference artifacts, not only console snippets

## Support and escalation hygiene

- [ ] Team knows what to include in a support issue (OS, Python version, commands, artifacts)
- [ ] Team uses a consistent issue template for install/runtime failures
- [ ] Escalation path is documented for blocked releases
