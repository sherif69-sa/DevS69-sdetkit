# Big-Brain Toolkit Roadmap

This roadmap converts the recent adaptive-diagnosis work into a product plan for making SDETKit feel like a serious, evidence-first engineering copilot instead of a static CI helper.

The goal is not to hard-code millions of brittle rules. The goal is to combine a seeded scenario catalog, repo-specific learning memory, generated evidence, and safe remediation policy so each run answers four questions:

1. **What happened?** Detect the first real failure signal, not just any non-empty log.
2. **What is the most likely scenario?** Rank candidate failure families across CI, test, dependency, environment, security, release, and docs lanes.
3. **What should a human check first?** Produce the smallest review-first checklist and proof commands.
4. **What can be fixed safely?** Allow automation only for narrow, proven, mechanical changes.

## Current strengths after the latest kit run

| Strength | Why it matters | Current proof surface |
| --- | --- | --- |
| Evidence-first adaptive diagnosis | Green logs stay clear, while real unclassified failures remain review-first. | `adaptive_diagnosis.analyze_evidence()` emits `clear` for no-signal evidence and `UNKNOWN_REVIEW_REQUIRED` only for failure-like evidence. |
| Seeded scenario intelligence | First runs no longer start from zero; they start from a catalog of common CI and quality failures. | `SEEDED_SCENARIO_DB` covers pytest, Ruff, mypy, coverage, package installs, policy gates, Docker, security, release, docs, platform, cache, network, and time-related failures. |
| Combinatorial odds coverage | The kit can reason over a billion-plus environment/scenario combinations without storing a billion static rows. | `ODDS_EXPANSION_AXES` multiplies scenario count, failure signals, runners, Python versions, dependency states, filesystems, network states, test shapes, runtime states, and change types. |
| Review-first safety posture | Unknown failures do not become safe auto-fix candidates by accident. | `safe_to_auto_fix` remains limited to the narrow safe allowlist. |
| Actionable first checks | Unknown review output includes candidate scenarios, checks, and proof commands instead of a generic warning. | Candidate evidence includes `candidate_scenarios=...` and `candidate_odds=...`. |
| Documentation and operator posture | The repo already has strong docs, adoption paths, evidence references, CI guidance, release/process docs, and roadmap structure. | MkDocs navigation exposes first-proof, operator/evidence, reference, advanced, and roadmap sections. |

## What still needs to become stronger

| Gap | Risk if ignored | Upgrade direction |
| --- | --- | --- |
| Scenario data is still embedded in Python | The catalog grows harder to review, version, extend, and ship as packs. | Move scenario definitions to versioned JSON/YAML rule packs with schema validation. |
| Candidate scoring is heuristic-only | Similar signals can rank confusingly when logs are noisy. | Add weighted scoring using historical outcomes, repo-local memory, and confidence calibration. |
| Learning memory is not yet fully closed-loop with scenario outcomes | The kit can suggest candidates, but it does not yet continuously promote/demote scenarios based on whether fixes worked. | Record accepted diagnosis, applied fix, proof command result, recurrence, and false-positive feedback. |
| Remediation remains narrow | This is safe, but users will want more assisted fixes after trust builds. | Add staged remediation lanes: explain-only, patch-plan, dry-run patch, guarded same-repo PR, and post-fix proof. |
| Evidence UI can still be easier to consume | Large JSON is powerful but not always persuasive for new users. | Add compact dashboards, markdown summaries, and PR comment sections that show evidence progression. |
| Multi-repo and enterprise pack behavior needs stronger contracts | Teams need repeatable policy and learning across many repositories. | Add organization-level scenario packs, policy overlays, shared learning exports, and privacy-preserving aggregation. |
| Benchmarking and demos need more real failure fixtures | A powerful product needs believable proof, not only unit tests. | Add fixture suites for common CI failures and publish before/after case studies. |

## Next upgrade roadmap

### Phase 1 — Externalize the big-brain database

**Outcome:** the seeded brain becomes a maintainable data product.

- Add `schemas/adaptive-scenario-pack.schema.json`.
- Move the built-in scenario catalog to `src/sdetkit/data/adaptive_scenarios.json` or `yaml`.
- Add loader validation with stable fields: `code`, `title`, `signals`, `keywords`, `checks`, `commands`, `risk_band`, `prior_weight`, and optional `tags`.
- Support layered packs:
  - built-in SDETKit pack,
  - repo-local `.sdetkit/adaptive/scenarios.json`,
  - organization pack,
  - private enterprise pack.
- Add tests that reject malformed packs and prove deterministic ordering.

### Phase 2 — Close the learning loop

**Outcome:** the kit learns from actual run outcomes, not only from seed data.

- Record every adaptive diagnosis attempt as a learning event:
  - matched signals,
  - candidate scenarios,
  - selected primary diagnosis,
  - recommended checks,
  - proof commands,
  - whether proof passed,
  - whether fix was accepted,
  - recurrence count,
  - false-positive marker.
- Add promotion/demotion rules: **Done:** summaries now promote scenarios when proof/fix feedback succeeds, demote false positives, increase risk for recurring failures, and lower confidence for thin evidence.
- Add `sdetkit adaptive learn summarize` to show top recurring scenarios and weakest lanes. **Done:** the CLI now rolls JSONL diagnosis events into `top_recurring_scenarios` and `weakest_lanes`.

### Phase 3 — Build the trust-grade operator experience

**Outcome:** anyone trying the repo can see why SDETKit is valuable in one run.

- Add a single generated `build/sdetkit/operator-brief.md` containing: **Done via `sdetkit adaptive brief`.**
  - gate result,
  - adaptive diagnosis,
  - scenario candidates,
  - first proof command,
  - safe-fix decision,
  - next owner action.
- Add a short PR comment mode: **Done via `sdetkit adaptive brief --format comment`.**
  - green run: no fake adaptive block,
  - known safe mechanical issue: scoped auto-fix path,
  - unknown failure: review-first candidate scenarios and checks.
- Add screenshots or sample PR comments in docs for the top 10 scenarios.

### Phase 4 — Expand safe remediation without weakening safety

**Outcome:** more fixes are assisted, but unknown failures remain human-reviewed.

- Keep current safe auto-fix route narrow.
- Add a second lane: **assisted patch plan** for non-mechanical cases.
- Require four gates before any non-format PR automation:
  - deterministic reproduction,
  - scenario confidence threshold,
  - changed-file scope limit,
  - post-fix proof command.
- Add fix-audit records for every automated change.

### Phase 5 — Make it enterprise-scale

**Outcome:** SDETKit becomes a cross-repo quality intelligence layer.

- Add portfolio rollups:
  - top failing scenario families,
  - recurrence by repo,
  - flake hotspots,
  - dependency drift hotspots,
  - remediation success rate,
  - mean time to first actionable proof.
- Add governance controls:
  - pack approval workflow,
  - policy overrides,
  - security-sensitive scenario isolation,
  - anonymized learning export.
- Add adapters for GitHub Actions, GitLab, Jenkins, and local-only operation.

## Big-win differentiators to protect

1. **No fake intelligence.** If evidence is green, stay quiet.
2. **Unknown is review-first.** Unknown failure evidence must never be guessed into safe auto-fix.
3. **Proof commands are part of the product.** A diagnosis without a proof path is not enough.
4. **Learning is local and inspectable.** Teams should see what the kit learned and why.
5. **Scenario packs are versioned assets.** The brain should be reviewable, testable, and portable.
6. **Automation earns trust.** Start with diagnosis, then safe mechanical fixes, then guarded patch plans.

## Suggested immediate backlog

| Priority | Work item | Acceptance check |
| --- | --- | --- |
| P0 | Extract scenario DB to a schema-validated pack | Done: built-in scenarios now load from `src/sdetkit/data/adaptive_scenarios.json`, validate through loader rules, and are documented against `schemas/adaptive-scenario-pack.schema.json`. |
| P0 | Add learning event records for adaptive diagnosis | Done: `sdetkit adaptive learn record` writes JSONL events with matched signals, candidates, selected primary diagnosis, checks, proof commands, recurrence count, and outcome placeholders. |
| P0 | Add operator brief artifact | Done: `python -m sdetkit adaptive brief` generates `build/sdetkit/operator-brief.md` from gate, diagnosis, learning, and safe-fix artifacts. |
| P1 | Add fixture corpus for top scenarios | Tests cover at least 20 realistic log fixtures. |
| P1 | Add candidate confidence calibration | Done: adaptive diagnosis can consume learning-summary calibration to boost/demote candidate scenario ranking and emit `candidate_calibration` evidence. |
| P1 | Add docs demo gallery | Docs show green, safe-fix, unknown-review, and recurring-failure examples. |
| P2 | Add org-level pack overlay | Local and org packs merge deterministically with built-in scenarios. |
| P2 | Add portfolio rollup | Multiple adaptive diagnosis outputs roll into a top-risk scenario report. |

## Definition of “real big win”

SDETKit becomes a big win when a new repo can run one command and get:

- a trustworthy green/noise-free result when everything passes,
- a human-readable diagnosis when something fails,
- candidate scenarios that feel like they came from an experienced SDET,
- proof commands that narrow the fix immediately,
- safe automation only where the risk is genuinely mechanical,
- learning memory that gets better with every run,
- and a roadmap of evidence that engineering leaders can trust.
