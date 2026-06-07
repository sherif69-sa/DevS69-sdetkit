# Adaptive next-wave roadmap

The Adaptive Intelligence execution plan is complete. This next wave turns the completed adaptive foundation into deeper enterprise analytics, stronger remediation governance, and optional operator-facing product surfaces without weakening the review-first safety model.

## Completion baseline carried forward

| Completed Adaptive Intelligence lane | Proof surface to protect |
| --- | --- |
| Scenario packs and layered governance | `adaptive_diagnosis.load_layered_scenarios()`, `layered_scenario_pack_report()`, `validate_layered_scenario_packs()` |
| Learning loop and calibration | `sdetkit adaptive learn record`, `sdetkit adaptive learn summarize`, `candidate_calibration=...` evidence |
| Operator experience | `sdetkit adaptive brief`, PR comment output, example gallery, fixture corpus |
| Safe remediation expansion | safe-fix plans, assisted patch plans, fix-audit records, post-fix proof enforcement |
| Enterprise scale | portfolio rollup, enterprise governance report, anonymized export, integration-adapter contract validation |

## Next-wave priorities

| Priority | Work item | Outcome | Acceptance check |
| --- | --- | --- | --- |
| NW-P0 | Enterprise analytics rollup metrics | Convert portfolio and fix-audit evidence into leadership metrics. | **Done:** `sdetkit adaptive enterprise-analytics` reports remediation success rate, missing-proof rate, failed-proof rate, top recurring source codes, top risky repos, and mean time to proof when timestamps are available. |
| NW-P0 | Remediation governance policy pack | Make remediation guardrails configurable without allowing unknown auto-fix. | **Done:** `sdetkit adaptive remediation-policy` validates policy files, safe-fix plans, assisted patch plans, proof requirements, changed-file scope, and unsafe expansion attempts. |
| NW-P1 | Next-wave dashboard artifact | Produce a static local dashboard from adaptive artifacts. | **Done:** `sdetkit adaptive dashboard` emits `build/sdetkit/adaptive-dashboard.html` with local links for diagnosis, brief, portfolio, fix-audit, governance, adapter, analytics, and remediation-policy artifacts. |
| NW-P1 | Cross-repo anonymized learning import | Let teams consume anonymized organization learning without exposing repo details. | **Done:** `sdetkit adaptive learning-import` validates redaction policy, rejects raw paths/private identifiers, and emits local calibration hints. |
| NW-P2 | Hosted/managed readiness boundary | Define what can be hosted later and what stays local-only. | **Done:** hosted readiness boundary docs separate local-only evidence, optional managed inputs, privacy controls, and unsupported data classes. |

## Current next-wave progress

| Completed next-wave items | Total tracked items | Progress | Latest completed item |
| ---: | ---: | ---: | --- |
| 5 | 5 | 100% | Cross-repo anonymized learning import and hosted readiness boundary. |

## Latest completed next-wave PR

**PR:** `Finalize adaptive next-wave learning import and readiness boundary`

**Delivered:**

1. Added `sdetkit adaptive learning-import` for anonymized cross-repo learning validation and calibration hints.
2. Rejects unredacted private fields, raw paths, and private file identifiers before import.
3. Added hosted/managed readiness boundary docs for local-only evidence, optional managed inputs, privacy controls, and unsupported data classes.
4. Completed the adaptive next-wave roadmap at 5 / 5 items.

## Next-wave completion status

The adaptive next wave is complete. Future PRs should focus on hardening, operator feedback, and bug fixes rather than expanding hosted behavior before the readiness boundary controls are implemented.

## Guardrails for the next wave

1. Do not turn unknown review-required diagnoses into automatic fixes.
2. Keep every analytics output traceable to local JSON/JSONL evidence.
3. Redact repo-private identifiers before any cross-repo learning export or import.
4. Prefer deterministic static artifacts over hosted behavior until privacy boundaries are documented.
5. Keep every new lane represented in CLI help and docs navigation.

## Progress tracking rule

Every next-wave PR should update this page with:

- completed next-wave item count,
- exact progress percentage,
- latest completed item,
- next recommended PR,
- validation commands.
