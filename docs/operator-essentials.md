# Operator essentials

This is the day-to-day SDETKit runbook. Keep it small: prove the release decision first, investigate failures second, and only consider guarded remediation after the evidence is attached.

If a team is new to SDETKit, start here first and expand only after this lane is deterministic in local and CI.

## Safety baseline

Investigation, reporting, recommendation, and planning paths are diagnostic-only by default. They recommend proof commands and next actions; they do not approve mutation.

Use this rule for every lane on this page:

```text
prove first -> diagnose from artifacts -> remediate only through explicit guarded policy
```

## Day 0 — First run and artifact handoff

Run the canonical release-confidence path first:

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor --format json --out build/doctor.json
```

Expected first artifacts:

- `build/gate-fast.json`
- `build/release-preflight.json`
- `build/doctor.json`

Read `ok` and `failed_steps` before raw logs. For artifact meanings, use [Artifact reference and generated sample map](artifact-reference.md).

## Day 1 — Failed CI or PR check triage

When a log, check, or gate fails, collect evidence without mutating the repository:

```bash
python -m sdetkit review . --no-workspace --format operator-json
python -m sdetkit investigate failure --log build/quality.log --format markdown
python -m sdetkit investigate failure --log build/quality.log --format json --out build/investigation/failure.json

# One-shot handoff bundle when the operator needs diagnosis, comment, learning, safe-fix boundary, and brief artifacts together.
python -m sdetkit adaptive failure-bundle \
  --log build/quality.log \
  --out-dir build/sdetkit/failure-intelligence \
  --proof-failed
```

Read these fields first in investigation output:

- `classification`
- `summary`
- `next_actions`
- `proof_commands`
- `diagnostic_only`
- `automation_allowed`
- `requires_human_review`

If the owner is unclear, narrow the repository surface:

```bash
python -m sdetkit investigate repo --root . --format json --out build/investigation/repo.json
python -m sdetkit investigate surface --root . --surface <surface> --format markdown
```

See [Investigation operator guide](investigation-operator-guide.md) for the complete diagnostic-only flow.

For bounded local processing of already-created diagnostic jobs, use the [Local diagnostic queue operator guide](local-diagnostic-queue-operator-guide.md). This path is local, reporting-only, explicitly bounded by `--max-jobs`, and stops after the first failed job without retrying it.

## Day 2 — Maintenance/autopilot artifact review

For maintenance-autopilot runs, start with the uploaded artifact bundle rather than individual logs:

1. Open `build/maintenance/autopilot/autopilot-report.md` for the run summary.
2. Open `build/maintenance/autopilot/adaptive-diagnosis.md` for the failure explanation and proof commands.
3. Open `build/maintenance/autopilot/safe-fix-plan.json` only as audit evidence.
4. Check `.sdetkit/maintenance/failure-memory.jsonl` and `.sdetkit/maintenance/adaptive-safe-fix-memory.jsonl` for recurring patterns.

A safe-fix plan is not permission to apply a fix. Treat candidate, probation, policy proposal, dry-run, and guardrail outputs as evidence until a reviewed policy path explicitly authorizes the next step.

## Day 3 — Guarded remediation review

Use remediation docs only after the diagnostic artifacts identify a specific failure class:

- [Remediation cookbook](remediation-cookbook.md) for first-failure playbooks.
- [Premium quality gate](premium-quality-gate.md) for guarded quality-gate remediation posture.
- [PR automation for audit auto-fixes](pr-automation.md) for explicit opt-in PR-fix behavior.

Before any mutation, confirm all of the following are true:

1. The branch is not `main`.
2. The policy path explicitly allows the guarded lane.
3. The generated plan and diff are attached to the PR or workflow run.
4. The proof command from the investigation output has been rerun on the reviewed branch.

## Rollout and CI contract commands (secondary)

These commands are kept here for rollout contract visibility, not as the first-time operator path:

- `python scripts/validate_enterprise_contracts.py`
- `python scripts/check_primary_docs_map.py`
- `make operations-baseline`
- `make operations-status`
- `make operations-next-action`
- `make operations-complete`
- `make release-readiness-start`
- `make release-readiness-workflow`
- `make release-readiness-status`
- `make release-readiness-start-contract`
- `make release-readiness-seed`
- `make release-readiness-complete`
- `make release-readiness-progress`
- `make release-readiness-surface-clarity`
- `make quality-contract-check`
- `make governance-contract-check`
- `make ecosystem-contract-check`
- `make scale-readiness-start`
- `make scale-readiness-status`
- `make scale-readiness-progress`
- `make scale-readiness-complete`
- `make metrics-contract-check`

## Expansion trigger rules

Expand beyond this page only when all of the following are true:

1. Day-0 commands are deterministic in local and CI.
2. Release artifacts are reviewed before raw logs.
3. Blockers are triaged from machine-readable fields (`ok`, `failed_steps`, `diagnostic_only`, `automation_allowed`) first.

## Next-step expansion map

After operator essentials is stable, expand in this order:

1. Investigation and diagnosis: [Investigation operator guide](investigation-operator-guide.md) -> [Adaptive Diagnosis Intelligence](adaptive-diagnosis.md) -> [Remediation cookbook](remediation-cookbook.md).
2. Artifact interpretation: [Artifact reference and generated sample map](artifact-reference.md) -> [CI artifact walkthrough](ci-artifact-walkthrough.md).
3. Quality gates: [Premium quality gate](premium-quality-gate.md) -> [Security gate](security-gate.md) -> [Determinism checklist](determinism-checklist.md).
4. Advanced inspection lanes (`inspect`, `inspect-compare`, `inspect-project`) only when needed.
5. Migration/legacy compatibility lanes only when required.
