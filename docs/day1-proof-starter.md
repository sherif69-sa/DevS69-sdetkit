# Day 1 proof starter (copy/paste)

If you feel stuck, use this exact flow.

## Step 1) Generate artifacts

Run:

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor
```

## Step 2) Open your first Value proof report

Open:

<https://github.com/sherif69-sa/DevS69-sdetkit/issues/new?template=value_proof_report.yml>

Use this text:

```text
Context:
Ran canonical Day 1 onboarding flow for deterministic release-confidence check.

Artifact paths:
- build/gate-fast.json
- build/release-preflight.json

First failing step (if no-ship):
n/a

Action taken:
Captured outputs and validated docs flow for first-time operator usage.

Outcome after rerun:
Confirmed artifact generation path and documented next remediation/follow-up actions.
```

## Step 3) Add your first proof-log entry

Append this to `docs/proof-log.md`:

```md
### 2026-04-21 — Day 1 starter proof run
- Context: first structured proof run using canonical path.
- Signal: ship/no-ship (fill this from artifact `ok` fields).
- Artifact(s): `build/gate-fast.json`, `build/release-preflight.json`.
- Action taken: opened value-proof issue and captured deterministic outputs.
- Outcome: baseline proof entry created for sprint tracking.
- Link: <issue-or-pr-link>
```

## Step 4) Mark daily sprint done

In `docs/proof-sprint-checklist.md`, check off Day 1 tasks and add KPI row values.

## Optional Step 5) Adaptive reviewer + intelligence pass

If you want higher-trust review signals, run:

```bash
make adaptive-premerge
```

Then include these fields in your proof issue when available:

- `judgment_summary`
- `judgment_next_move`
- confidence score (for example `0.97`)
