# Adaptive Intelligence Toolkit progress tracker

This tracker keeps the Adaptive Intelligence Toolkit roadmap measurable after every follow-up PR. It is the quick answer for: **how much did we achieve, what changed in the latest pass, what should the next PR do, and what follow-ups must stay on track?**

## Current progress snapshot

| Scope | Completed | Total | Progress | Status |
| --- | ---: | ---: | ---: | --- |
| Immediate backlog | 8 | 8 | 100% | Immediate backlog complete; continue into Operational readiness/5 follow-ups. |
| Baseline readiness — Externalize the adaptive intelligence database | 4 | 4 | 100% | Built-in scenarios are data-backed and schema validated. |
| Release readiness — Close the learning loop | 3 | 3 | 100% | Learning records, summaries, promotion/exampletion, and calibration are active. |
| Platform readiness — Trust-grade operator experience | 3 | 3 | 100% | Operator brief, PR comment mode, and example gallery are complete. |
| Operational readiness — Safe remediation expansion | 4 | 4 | 100% | Safe-fix, assisted patch-plan, fix-audit records, and proof enforcement are in place. |
| Adoption readiness — Enterprise scale | 3 | 3 | 100% | Portfolio rollup, enterprise governance controls, and adapter hardening are complete. |

## Completed immediate-backlog items

| Priority | Completed item | Proof surface |
| --- | --- | --- |
| P0 | Extract scenario DB to a schema-validated pack. | `src/sdetkit/data/adaptive_scenarios.json`, `schemas/adaptive-scenario-pack.schema.json`, loader validation tests. |
| P0 | Add learning event records for adaptive diagnosis. | `sdetkit adaptive learn record` JSONL events. |
| P0 | Add operator brief artifact. | `sdetkit adaptive brief` with Markdown, JSON, and PR comment outputs. |
| P1 | Add candidate confidence calibration. | `candidate_calibration=...` evidence in adaptive diagnosis output. |
| P1 | Add docs example gallery. | `docs/adaptive-product-proof-gallery.md` with green, safe-fix, unknown-review, recurring-learning, and portfolio examples. |
| P1 | Add fixture corpus for top scenarios. | `tests/fixtures/adaptive_logs/` plus parametrized coverage for 20 realistic adaptive failure logs. |
| P2 | Add portfolio rollup. | `sdetkit adaptive portfolio-rollup` with top-risk scenarios, recurrence by repo, and next owner action. |
| P2 | Harden org-level pack overlay. | Layer metadata, override approval validation, and governance docs for org/private scenario packs. |

## Remaining immediate-backlog items

All immediate backlog items are complete. Continue with the Operational readiness/5 follow-up queue below.

## Latest progress made

The latest pass finalized the adaptive next wave by adding anonymized learning import validation and the hosted/managed readiness boundary. Operators can now reject unredacted cross-repo learning inputs, emit local calibration hints, and rely on documented local-only versus optional-managed data boundaries.

## Next-wave progress snapshot

| Scope | Completed | Total | Progress | Status |
| --- | ---: | ---: | ---: | --- |
| Adaptive next wave | 5 | 5 | 100% | Next-wave analytics, remediation policy, dashboard, anonymized import, and hosted readiness boundary are complete. |

## Latest next-wave completion

**Completed PR:** `Finalize adaptive next-wave learning import and readiness boundary`

**Delivered:** cross-repo anonymized learning import validation, privacy-safe calibration hints, and hosted/managed readiness boundary docs. The adaptive next wave is now complete at 5 / 5 items.

**Validation commands:**

1. `PYTHONPATH=src python -m pytest tests/test_adaptive_learning_import.py`
2. `PYTHONPATH=src python -m pytest tests/test_docs_navigation.py tests/test_adaptive_learning_import.py tests/test_adaptive_dashboard.py tests/test_adaptive_enterprise_governance.py`

## Latest stabilization pass

**Completed PR:** `Harden adaptive learning import privacy checks`

**Goal:** keep the completed next-wave feature set stable through targeted redaction hardening rather than new hosted behavior.

**Delivered:**

1. Learning import now rejects private URLs, hostnames, and email addresses in addition to raw paths/files.
2. Regression tests cover the new operator feedback privacy examples.
3. Hosted behavior remains out of scope until readiness controls are implemented and tested.

## Follow-up PR queue

| Order | Suggested PR | Target progress impact | Notes |
| ---: | --- | --- | --- |
| 1 | Continue adaptive next-wave operator feedback hardening. | Maintains 100% completion. | Bug fixes, redaction examples, and docs polish for completed local-only adaptive lanes. |

## Operating rule for future updates

Every Adaptive Intelligence follow-up PR should update this file with:

1. progress percentage after the PR,
2. what was completed in that pass,
3. the recommended next PR,
4. remaining follow-ups and risk notes,
5. the exact commands used to validate the update.
