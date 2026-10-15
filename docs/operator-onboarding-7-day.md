# Operator Onboarding (7-Day Practical Plan)

This plan helps new operators adopt SDETKit with deterministic evidence and fast feedback. Every command on this page exists today; `make help` lists the make targets.

## Day 1 — First proof baseline

- `make first-proof`
- `make first-proof-verify`

## Day 2 — Readiness visibility

- `python -m sdetkit doctor --format md`
- `python -m sdetkit fit --root . --format json --out build/sdetkit-fit-recommendation.json`

## Day 3 — Daily gate rhythm

- `python -m sdetkit gate fast --format json --out build/gate-fast.json`
- Read `verdict` and `failed_steps` before raw logs.

## Day 4 — Pre-merge confidence

- `python -m sdetkit gate release --reuse-fast build/gate-fast.json --format json --out build/gate-release.json`
- `python -m sdetkit verify merge --checks-json <checks.json> --evidence build/gate-release.json`

## Day 5 — First failure through the remediation loop

- Save a failing CI job's log, then `python -m sdetkit diagnose run --log <ci-log> --prove`
- Read `build/sdetkit/remediation-loop/decision-card.md`

## Day 6 — Decide and learn

- `python -m sdetkit diagnose decide --card build/sdetkit/remediation-loop/decision-card.json --approve --reviewer <you>` (or `--reject`)
- `python -m sdetkit diagnose memory` to see what the history has proven

## Day 7 — Team handoff and cadence

- `python -m sdetkit adoption --history build/adoption-history.jsonl --format md`
- Align on a daily gate and weekly review cadence
