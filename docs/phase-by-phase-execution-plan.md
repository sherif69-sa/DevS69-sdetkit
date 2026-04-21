# Phase-by-phase execution plan (major upgrade track)

Run this plan in sequence and ship concrete outputs in every phase.

## Program guardrails

- Keep the decision backbone fixed: `gate fast -> gate release -> doctor`.
- Keep tier boundaries clear: Public/stable first, advanced/supporting next, transition/legacy secondary.
- Ship measurable deltas in each phase (artifacts, KPIs, contracts, docs updates).

---

## Phase 1 — Build the baseline execution lane

### Mission
Stand up a baseline lane that always produces machine-readable evidence and immediately flags environment/tooling drift.

### Do this
- Lock environment contracts (Python/toolchain expectations).
- Automate the baseline lane and capture artifacts.
- Create a quality debt register (lint/test/contract failures) with direct owners.
- Publish a weekly baseline report.

### Execute now
1. Run the baseline lane:
   - `make phase1-baseline`
   - `make phase1-status`
   - `make phase1-next`
   - `make phase1-complete`
   - or `bash scripts/phase1_baseline_lane.sh`
2. Capture outputs under `build/phase1-baseline/`:
   - `gate-fast.json`
   - `release-preflight.json`
   - `doctor.json`
   - per-check logs and return codes
   - summary JSON + markdown
3. Convert blockers into assigned remediation tasks with due dates.
4. Execute the top remediation task in the same cycle and rerun `make phase1-status`.

### Done when
- CI and local runs are deterministic (same command path, same artifact contract).
- Every baseline step emits logs and summary payloads.
- Top blocking quality debt items are ranked, assigned, and reduced every cycle.

### Next upgrades
- Multi-Python matrix baseline evidence.
- Profile-aware baseline (quick/standard/strict) comparisons.
- Cross-repo baseline federation for portfolio reporting.

### Close out
- Freeze Phase 1 as complete in weekly reporting.
- Keep baseline artifacts as immutable audit evidence.
- Remove stale Phase 1 TODOs from active execution boards.

---

## Phase 2 — Simplify surfaces and commands

### Mission
Cut onboarding confusion while preserving advanced operational power.

### Do this
- Streamline first-contact docs and help surfaces.
- Tighten command-family guidance by outcome.
- Improve migration guidance for transition-era lanes.

### Execute now
1. Build an "operator essentials" command map.
2. Collapse repetitive docs paths into canonical flows.
3. Add explicit migration tables for legacy/transition surfaces.
4. Introduce docs consistency checks for start-here + CI + triage routes.

### Done when
- A new operator reaches first successful run through one unambiguous path.
- Command discoverability matches product tiers with minimal confusion.
- Legacy routing is documented, predictable, and non-disruptive.

### Next upgrades
- Persona-specific docs overlays (maintainer/operator/executive).
- Interactive CLI onboarding workflows.
- Auto-generated docs nav health score.

---

## Phase 3 — Expand the quality engine

### Mission
Upgrade checks into a stronger execution engine with better recommendations and richer evidence payloads.

### Do this
- Mature adaptive check planning.
- Improve remediation outputs.
- Improve run-report analytics and trend comparisons.

### Execute now
1. Extend adaptive planning signals (changed paths, reasons, risk areas).
2. Enrich risk summary/fix plan payload contracts.
3. Add trend deltas across successive baseline runs.
4. Improve doctor handoff signals for deterministic next-pass actions.
5. Validate baseline summary schema with:
   - `make phase3-quality-contract`
   - `python scripts/check_phase1_baseline_summary_contract.py --summary build/phase1-baseline/phase1-baseline-summary.json --format json`

### Done when
- Mean-time-to-triage drops through machine-readable outputs.
- Recommendation precision improves in failure scenarios.
- Output contracts stay stable and versioned for operator tooling.

### Next upgrades
- Intelligent check selection by repository topology.
- Failure-family clustering and root-cause acceleration.
- Fleet-level quality risk heatmaps.

---

## Phase 4 — Enforce enterprise governance

### Mission
Turn technical capability into enterprise-grade confidence with explicit governance and audit evidence.

### Do this
- Harden contract governance.
- Enforce policy and compatibility discipline.
- Produce release-room evidence bundles.

### Execute now
1. Expand enterprise contract validations in CI gates.
2. Standardize release-room summaries and evidence retention windows.
3. Document compatibility/deprecation boundaries per tier.
4. Track governance adherence with recurring reviews.
5. Enforce governance docs contract with:
   - `make phase4-governance-contract`
   - `python scripts/check_phase4_governance_contract.py --format json`

### Done when
- Enterprise checks are reproducible and policy-aligned.
- Governance evidence is available and auditable.
- Compatibility expectations are clear to integrators.

### Next upgrades
- Compliance overlay packs (domain-specific).
- Policy-as-code templates for partner repos.
- Automated governance drift alerts.

---

## Phase 5 — Scale ecosystem integrations

### Mission
Scale integrations and extension surfaces without destabilizing core release-confidence guarantees.

### Do this
- Improve plugin/runtime extension reliability.
- Standardize integration playbooks.
- Ship partner-ready packaging and support artifacts.

### Execute now
1. Harden plugin onboarding and failure diagnostics.
2. Expand integration quickstarts with contract-backed checks.
3. Publish extension certification criteria.
4. Build portfolio scorecards from shared evidence contracts.
5. Enforce ecosystem contract with:
   - `make phase5-ecosystem-contract`
   - `python scripts/check_phase5_ecosystem_contract.py --format json`

### Done when
- Integrations remain optional, reliable, and version-aware.
- Extension failures are visible and non-blocking by default.
- Partner onboarding time drops through repeatable playbooks.

### Next upgrades
- Marketplace-style extension catalog.
- Hosted control-plane integrations.
- Managed adoption analytics across organizations.

---

## Phase 6 — Operationalize metrics and commercialization

### Mission
Convert technical progress into repeatable business outcomes and reporting-ready metrics for operators, buyers, and investors.

### Do this
- Generate KPI snapshots and scorecards.
- Validate metrics contracts for recurring reporting.
- Publish commercialization-ready evidence surfaces.

### Execute now
1. Build and publish periodic KPI snapshots.
2. Standardize scorecard freshness and publishing cadence.
3. Tie release-confidence outputs to adoption/operations metrics.
4. Enforce metrics contract with:
   - `make phase6-metrics-contract`
   - `python scripts/check_phase6_metrics_contract.py --format json`

### Done when
- KPI artifacts are generated on schedule and contract-validated.
- Metrics signals are reproducible and tied to release-confidence behavior.
- Reporting surfaces are usable in quarterly portfolio/leadership reviews.

### Next upgrades
- Trend anomaly alerts for KPI regressions.
- Portfolio-level cross-repo reporting federation.
- Commercial package variants with benchmark slices.

---

## Phase control loop (run every phase)

Run the same control loop in every phase:

1. Plan: set targets, risks, and metrics.
2. Execute: ship lane automation and deliverables.
3. Validate: run contract checks and baseline verification.
4. Publish: emit artifacts, summary, and decision memo.
5. Expand: queue the next major upgrades.

This keeps the roadmap sequential while still open for large-scale iteration.
