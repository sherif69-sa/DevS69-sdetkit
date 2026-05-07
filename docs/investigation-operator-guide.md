# Investigation operator guide

Use the investigation front door when a CI log, PR check, or maintenance run needs human triage before any remediation is attempted.

The investigation lane is intentionally report-only. It explains the failure, recommends the next proof command, and records the safety posture. It does not create branches, push commits, open pull requests, or apply fixes.

## Failure log triage

Start with the failure command when you have a saved log:

```bash
python -m sdetkit investigate failure --log build/quality.log --format markdown
```

For machine-readable output:

```bash
python -m sdetkit investigate failure \
  --log build/quality.log \
  --format json \
  --out build/investigation/failure.json
```

Read these fields first:

- `classification`
- `summary`
- `why_it_matters`
- `next_actions`
- `proof_commands`
- `memory_lookup_key`
- `diagnostic_only`
- `automation_allowed`
- `safe_to_auto_fix`
- `requires_human_review`

A normal operator-facing investigation should keep `diagnostic_only` set to `true` and `automation_allowed` set to `false`.

## Repository and surface narrowing

Use the repository summary when you do not yet know which area owns the failure:

```bash
python -m sdetkit investigate repo --root . --format json --out build/investigation/repo.json
```

Use the surface command after the repo summary points at a likely area:

```bash
python -m sdetkit investigate surface \
  --root . \
  --surface netclient \
  --format markdown \
  --out build/investigation/netclient.md
```

The surface result should help narrow the next focused test or proof command. It is still diagnostic-only.

## Maintenance autopilot artifacts

Maintenance autopilot uploads the investigation and safe-fix audit artifacts when they are produced. Start with:

- `build/maintenance/autopilot/autopilot-report.json`
- `build/maintenance/autopilot/autopilot-report.md`
- `build/maintenance/autopilot/adaptive-diagnosis.json`
- `build/maintenance/autopilot/adaptive-diagnosis.md`
- `build/maintenance/autopilot/safe-fix-plan.json`
- `build/maintenance/autopilot/adaptive-safe-remediation-result.json`
- `build/maintenance/autopilot/adaptive-safe-commit-result.json`
- `.sdetkit/maintenance/failure-memory.jsonl`
- `.sdetkit/maintenance/adaptive-safe-fix-memory.jsonl`

Treat safe-fix, candidate, probation, policy proposal, dry-run, and guardrail outputs as audit evidence unless a separate reviewed policy path explicitly authorizes the next step.

## Safety interpretation

The investigation chain may recommend commands, list candidate classes, or build a dry-run plan. Those outputs are not permission to mutate the repository.

Use this rule of thumb:

```text
diagnose and plan first; mutate only after explicit reviewed guardrails allow it
```

Before any fix is applied, confirm:

1. the payload still says `automation_allowed: false` unless a specific guarded lane is being reviewed;
2. `auto_fix_allowed_now` is not treated as approval unless the policy and PR-only guardrails are also satisfied;
3. the proof command is run on the exact branch being reviewed;
4. generated artifacts are attached to the PR or workflow run;
5. no direct push to `main` is part of the investigation path.

## Common operator flow

```bash
python -m sdetkit investigate failure --log build/quality.log --format markdown
python -m sdetkit investigate repo --root . --format json --out build/investigation/repo.json
python -m sdetkit investigate surface --root . --surface netclient --format markdown
PYTHONPATH=src python -m pytest -q tests/test_netclient_envelope_parity.py
```

If the focused proof passes, update the PR with the investigation summary and proof command. If it fails, keep the failure log and rerun `investigate failure` on the new evidence.
