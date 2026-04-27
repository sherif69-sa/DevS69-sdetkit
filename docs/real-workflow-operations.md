# Real workflow operations (production-first)

This is the **live operating workflow** for running SDETKit on a real repository.

No educational naming, no planning theater: this page is for execution.

## Mission

Run one deterministic release-confidence loop that answers:

- Are we ready to ship now?
- If not, what failed first?
- What is the next highest-impact remediation?

## Command lanes

### 1) Daily gate lane (required)

```bash
make real-workflow-daily
# alias:
make ops-daily
make ops-daily-fast  # skips reinstall lane; uses current .venv
```

By default, local first-proof lanes run release gate with `--dry-run` (`FIRST_PROOF_RELEASE_DRY_RUN=true`) to avoid clean-tree blocking during active development.

Outputs (source of truth):

- `build/first-proof/first-proof-summary.json`
- `build/first-proof/first-proof-learning-db.jsonl`
- `build/first-proof/first-proof-learning-rollup.json`
- `build/first-proof/control-tower.json`
- `build/first-proof/weekly-trend.json`
- `build/first-proof/weekly-threshold-check.json`
- `build/ops/followup.json`
- `build/ops/followup.md`
- `build/ops/followup-history.jsonl`
- `build/ops/followup-history-rollup.json`
- `build/ops/followup-contract-check.json`

### 2) Weekly operations lane (required)

```bash
make real-workflow-weekly
# alias:
make ops-weekly
```

Purpose:

- refresh adaptive postcheck guidance
- regenerate top-tier reporting bundle
- validate enterprise/readiness contract health

### 3) Pre-merge release lane (required)

```bash
make real-workflow-premerge
# alias:
make ops-premerge
make ops-premerge-fast  # uses ship-readiness --release-dry-run for local rehearsal
make ops-premerge-next  # run premerge + print concise next actions
make ops-premerge-next-fast  # run premerge-fast + print concise next actions
# if clean-tree is the blocker, ops-premerge-next recommends:
# OPS_NEXT_COMMAND=make ops-premerge-fast
```

`ops-premerge-fast` now runs the entire release-room lane with ship-readiness dry-run semantics.

Purpose:

- run pre-merge gate
- run release-room evidence checks
- block merge on unstable posture

### 4) Follow-up recommendations lane (auto-generated from daily lane)

```bash
make ops-followup
make ops-followup-contract
make ops-now        # full daily lane (gate + follow-up + contract)
make ops-now-lite   # follow-up + contract only
make ops-next       # print top 3 prioritized next actions
```

This emits prioritized recommendations every run so the next action is explicit.
It also appends follow-up history so recurring remediation themes are visible week-over-week.
Release-preflight failures (for example `doctor_release` clean-tree blockers) are elevated into explicit follow-up actions.
Contract for follow-up payloads: `docs/ops-followup-schema.v1.json`.

## Data model used in production

Treat repository artifacts as three production datasets:

1. **Event log dataset**
   - file: `build/first-proof/first-proof-learning-db.jsonl`
   - grain: one row per run
2. **Decision snapshot dataset**
   - file: `build/first-proof/first-proof-summary.json`
   - grain: one row per execution window
3. **Operations rollup dataset**
   - files: `first-proof-learning-rollup.json`, `control-tower.json`, `weekly-trend.json`
   - grain: one row per generated analytical summary

## KPI scorecard used for execution

Track these every week:

- ship rate (7d/30d)
- gate fast failure rate
- gate release failure rate
- doctor failure rate
- mean time to green
- rollback rate
- evidence pack coverage

If trends degrade for two consecutive windows, treat as incident-level reliability risk.

## Operational responsibilities

- **Engineer on duty:** runs `real-workflow-daily`, triages top failed steps.
- **Release owner:** runs `real-workflow-premerge` before merge/tag.
- **Program owner:** runs `real-workflow-weekly`, publishes KPI narrative.

## Exit criteria (workflow is healthy)

The workflow is healthy when all of the following are true:

1. Daily run produces deterministic SHIP/NO-SHIP with complete artifacts.
2. Weekly trend and threshold checks are generated and reviewed.
3. Pre-merge gate passes without bypass.
4. KPI/reporting artifacts are published on cadence.

## Decommissioning note

This page replaces planning-oriented strategy writeups for day-to-day operation.
Keep this document as the canonical execution reference and archive outdated planning docs.
