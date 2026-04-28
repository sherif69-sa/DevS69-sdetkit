# Business Execution Hub

This hub turns the business execution docs into a practical, one-by-one working sequence.

## Recommended execution order

1. [00 — Program master plan](00-program-master-plan.md)
2. [01 — ICP scoring matrix](01-icp-scoring-matrix.md)
3. [02 — Pricing logic v1](02-pricing-logic-v1.md)
4. [03 — GTM 30-day operating calendar](03-gtm-30-day-operating-calendar.md)
5. [04 — Moat and category strategy](04-moat-and-category-strategy.md)
6. [05 — 12-month execution roadmap](05-12-month-execution-roadmap.md)
7. [06 — KPI instrumentation and operating system](06-kpi-instrumentation-and-operating-system.md)
8. [07 — Design-partner and sales motion playbook](07-design-partner-and-sales-motion-playbook.md)
9. [08 — Merge readiness and execution checklist](08-merge-readiness-checklist.md)

## One-by-one implementation checklist

- [ ] Approve positioning + ICP weighting assumptions.
- [ ] Set weekly operating review owner and cadence.
- [ ] Adopt KPI definitions and threshold owners.
- [ ] Select pilot cohort and baseline metrics.
- [ ] Validate pricing guardrails and pilot commercial policy.
- [ ] Start 30-day calendar and publish weekly operating memos.
- [ ] Run month-close review and lock next-month priorities.

## Merge gate for this business pack

Before merge/use:

1. All docs are discoverable from docs navigation.
2. Team agrees on owners for weekly/monthly rhythms.
3. KPI threshold owners are named.
4. First pilot cohort is identified.
5. Execution checklist has an assigned accountable owner.

## Execute now (week-1 bootstrap)

Generate execution artifacts (JSON + operating memo) instead of staying at planning level:

```bash
make business-execution-start
make business-execution-start-contract
make business-execution-go-gate
make business-execution-progress
make business-execution-progress-contract
make business-execution-next
make business-execution-next-contract
make business-execution-handoff
make business-execution-handoff-contract
make business-execution-escalation
make business-execution-escalation-contract
make business-execution-followup
make business-execution-followup-contract
make business-execution-continue
make business-execution-continue-contract
make business-execution-inputs-contract
make business-execution-pipeline
make business-execution-week1-pipeline
```

Default repo operator for make-based business execution commands is `sherif69-sa` (`BUSINESS_EXECUTION_OPERATOR` in Makefile), so one operator owns all generated execution roles unless you override it.

Default runtime outputs are written to:
- `build/business-execution/business-execution-week1.json`
- `build/business-execution/business-execution-week1-memo.md`
- `build/business-execution/business-execution-week1-progress.json`
- `build/business-execution/business-execution-week1-progress.md`
- `build/business-execution/business-execution-week1-progress-history.jsonl`
- `build/business-execution/business-execution-week1-progress-rollup.json`
- `build/business-execution/business-execution-week1-next.json`
- `build/business-execution/business-execution-week1-next.md`
- `build/business-execution/business-execution-handoff.json`
- `build/business-execution/business-execution-handoff.md`
- `build/business-execution/business-execution-escalation.json`
- `build/business-execution/business-execution-escalation.md`
- `build/business-execution/business-execution-followup.json`
- `build/business-execution/business-execution-followup.md`
- `build/business-execution/business-execution-followup-history.jsonl`
- `build/business-execution/business-execution-followup-rollup.json`
- `build/business-execution/business-execution-continue.json`
- `build/business-execution/business-execution-continue.md`
- `build/business-execution/business-execution-inputs.json`

Or run directly with named owners:

```bash
python scripts/business_execution_start.py \
  --start-date 2026-04-28 \
  --program-owner "Founder/GM" \
  --gtm-owner "GTM Lead" \
  --commercial-owner "Commercial Lead" \
  --solutions-owner "Solutions Lead" \
  --ops-owner "Ops Analyst"
```

If you want to run everything as a single operator (only you own all actions), use:

```bash
python scripts/business_execution_start.py --single-operator "Your Name"
```

Execution status is automatic:
- `go` when all owners are assigned.
- `needs-owner-assignment` when one or more owners are still `TBD`.

To fail fast when ownership is incomplete:

```bash
python scripts/business_execution_start.py --strict-owner-assignment
```

Generate a day-by-day progress scorecard and gate summary:

```bash
python scripts/business_execution_progress.py \
  --done "Confirm owners and operating cadence." \
  --done "Finalize ICP shortlist."
```

Progress owner-gate behavior:
- Default is `--owner-gate-mode relaxed` so execution can continue before all owners are assigned.
- Use `--owner-gate-mode strict` when you want missing owners to force a `fail` gate.

Validate progress artifact contract:

```bash
python scripts/check_business_execution_progress_contract.py
```

Generate prioritized next tasks from progress:

```bash
python scripts/business_execution_next.py --limit 3
```

Validate next-actions contract:

```bash
python scripts/check_business_execution_next_contract.py
```

Generate an executive handoff summary:

```bash
python scripts/business_execution_handoff.py
```

Validate handoff contract:

```bash
python scripts/check_business_execution_handoff_contract.py
```

Generate execution escalation snapshot:

```bash
python scripts/business_execution_escalation.py
```

Validate escalation contract:

```bash
python scripts/check_business_execution_escalation_contract.py
```

Generate continuous follow-up actions (so execution keeps moving between checkpoints):

```bash
python scripts/business_execution_followup.py
```

This command also appends follow-up history, refreshes a rollup summary, and computes `next_checkpoint_at`, `checkpoint_status`, `checkpoint_due_in_hours`, and `checkpoint_command` so continuity can be tracked over time.

Validate follow-up contract:

```bash
python scripts/check_business_execution_followup_contract.py
```

Generate the next command decision artifact from follow-up:

```bash
python scripts/business_execution_continue.py
```

Validate continue-decision contract:

```bash
python scripts/check_business_execution_continue_contract.py
```

Run the full pipeline (all generation + all contracts) in one command:

```bash
python scripts/business_execution_pipeline.py
```

Single-operator pipeline mode:

```bash
python scripts/business_execution_pipeline.py --single-operator "Your Name"
```

Repository code ownership is mapped to `@sherif69-sa` for all files via `.github/CODEOWNERS`.

Attach external execution inputs (prompt + guidelines bundle) with traceable hashes:

```bash
python scripts/business_execution_pipeline.py \
  --challenge-prompt workflow_execution_prompt.md \
  --guidelines-zip workflow_execution_guidelines_bundle.zip
```

If those canonical filenames are present in the current working directory, the pipeline auto-discovers them and attaches them without extra flags.

Input bundle policy:
- Markdown input records heading + line count metadata.
- Guidelines zip records entry count + preview.
- Zip bundles with more than 25 files are rejected by the pipeline.
- External inputs must be supplied as a pair (prompt + zip) for reproducible runs.

Validate input manifest contract directly:

```bash
python scripts/check_business_execution_inputs_contract.py
```
