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

## Latest completed adoption update

**PR:** `feat(adoption): extract GitLab CI proof commands`

**Delivered:**

1. Added conservative read-only extraction of literal GitLab CI `script` proof commands from `.gitlab-ci.yml`.
2. Classified extracted commands as test, lint, type, security, docs, or unknown.
3. Preserved command source metadata for CI system, file, and job.
4. Kept includes, anchors, aliases, inherited behavior, multiline scripts, variables, and dynamic commands review-first instead of guessed.
5. Added regression coverage for literal GitLab CI scripts and unresolved dynamic GitLab CI constructs.
6. Merged only after all required gates were green: CI, GitHub Actions Advanced Reference, Repo Audit, Enterprise Gate, Premium Gate, Security, OSV, Dependency Audit, Dependency Review, maintenance-autopilot, First proof, branch protection, and PR Quality.

## Upcoming update wave

The next work should focus on hardening adoption, merge reliability, diagnostics, and operator trust. The goal is to make every future repo update easier to land cleanly, with fewer hidden CI surprises and a clearer proof trail.

| Priority | Lane | Work item | Outcome | Acceptance check |
| --- | --- | --- | --- | --- |
| UP-P0 | Green main and CI reliability | Full-suite failure visibility | Failed full-suite and matrix jobs should produce concise, downloadable first-failure artifacts instead of forcing operators to inspect truncated logs. | A failing `python -m pytest -q` run emits a short artifact with first failing test, traceback summary, environment, and reproduction command. |
| UP-P0 | Green main and CI reliability | Merge-readiness monitor | PRs should expose a single clean merge-readiness summary for required checks, action-required runs, bot-triggered runs, stale heads, and policy blockers. | A command or artifact reports required checks as `green`, `pending`, `failed`, or `action_required`, with next owner action. |
| UP-P0 | Package quality | Wheel and sdist footprint guardrail | Packaging failures should be caught before long Full CI and Advanced Reference matrix runs. | Package validation identifies duplicate module content, unexpected helper files, missing package data, and public-surface drift with exact file names. |
| UP-P1 | Product features | Adoption-surface provider parity | GitHub Actions, GitLab CI, Jenkins, and local scripts should have consistent read-only proof-command discovery semantics. | Fixture matrix covers literal commands, dynamic commands, inherited configuration, includes, anchors/aliases, and provider-specific unknowns. |
| UP-P1 | Test suite professionalism | Adoption fixture corpus expansion | Add realistic fixtures that prove adoption discovery across Python, JavaScript/TypeScript, Go, Rust, Java, .NET, docs, security, release, and mixed-CI repos. | Fixture tests assert detected languages, package managers, CI systems, proof commands, evidence metadata, and review-first unknowns. |
| UP-P1 | Docs and operator experience | Adoption-surface operator guide | Users should understand what the adoption surface can infer, what it refuses to guess, and which proof commands are safe to review manually. | Docs include examples for GitHub Actions, GitLab CI, Jenkins, dynamic scripts, and review-first unknown output. |
| UP-P1 | Operational intelligence | PR repair playbook from real incidents | Capture the lessons from the PR #2006 merge process so future fixes avoid config exclusions, temporary workflow debt, and unclean helper modules. | Add a troubleshooting section covering `ruff_format`, wheel duplicate content, action-required bot runs, full-suite coverage failures, and clean branch retriggers. |
| UP-P2 | Security posture | Workflow permission and temporary workflow guardrails | Temporary diagnostic or formatter workflows must not remain in final diffs, and their permissions must stay minimal. | Repo audit or docs checklist blocks/reminds on temporary workflow files, broad permissions, and unpinned actions. |
| UP-P2 | Release readiness | Roadmap-to-PR traceability | Every feature PR should say which roadmap lane it advances and what follow-up remains. | PR template or release checklist includes roadmap lane, KPI impact, validation commands, rollback path, and next recommended PR. |
| UP-P2 | Architecture health | Adoption module simplification | Keep adoption surface implementation in the public module unless a split has a clear packaging and coverage contract. | No compatibility shims or temporary implementation modules are introduced without package, coverage, and public-surface tests. |

## Upcoming KPI targets

| KPI | Target for upcoming updates | Evidence source |
| --- | --- | --- |
| `green_main_days_ratio` | Keep main green after every roadmap PR. | Required checks on `main` and PR merge history. |
| `mean_time_to_recover_red_main` | Reduce by adding first-failure artifacts and merge-readiness summaries. | CI run timestamps and failure diagnostics. |
| `ci_flake_count` | Track reruns separately from real source failures. | Workflow rerun records and diagnostic summaries. |
| `package_validation_status` | Stay green before Full CI starts. | Build, twine, wheel contents, and smoke install jobs. |
| `smoke_install_status` | Stay green on supported Python versions. | Wheel smoke install jobs for py3.11 and py3.12. |
| `workflow_permission_findings` | Keep temporary workflows out of final diffs and permissions minimal. | Repo audit and workflow contract reports. |
| `feature_regression_count` | Keep at zero by pairing every adoption provider enhancement with fixture coverage. | Adoption fixture matrix and provider parity tests. |
| `first_failure_extraction_accuracy` | Improve through concise full-suite failure artifacts. | Full-suite diagnostic artifacts and reviewed failures. |

## Recommended next PR sequence

1. **Full-suite failure visibility** — add concise pytest/coverage failure artifacts for long matrix jobs.
2. **Merge-readiness monitor** — add a local/CI artifact summarizing required checks and action-required runs.
3. **Adoption-surface provider parity** — extend proof-command extraction fixtures beyond GitLab CI.
4. **Adoption operator guide** — document proof-command discovery, review-first unknowns, and safe manual verification.
5. **PR repair playbook** — codify the lessons from the PR #2006 troubleshooting path.
6. **Roadmap-to-PR traceability** — make every future PR update this page or explicitly state why it does not.

## Validation commands for roadmap updates

Every roadmap update should be validated with the smallest relevant documentation and repo-health checks available:

```bash
python -m pytest -q tests/test_docs_qa.py -o addopts=
python -m pytest -q tests/test_adoption_surface.py tests/test_adoption_surface_gitlab_ci.py -o addopts=
python -m pre_commit run -a
```

## Next-wave completion status

The adaptive next wave is complete. Future PRs should focus on hardening, operator feedback, merge reliability, and bug fixes rather than expanding hosted behavior before the readiness boundary controls are implemented.

## Guardrails for the next wave

1. Do not turn unknown review-required diagnoses into automatic fixes.
2. Keep every analytics output traceable to local JSON/JSONL evidence.
3. Redact repo-private identifiers before any cross-repo learning export or import.
4. Prefer deterministic static artifacts over hosted behavior until privacy boundaries are documented.
5. Keep every new lane represented in CLI help and docs navigation.
6. Do not leave temporary workflows, marker files, config exclusions, or helper-module detours in the final diff.
7. Keep GitHub communication artifact-first; do not post automated PR comments unless explicitly requested.

## Progress tracking rule

Every next-wave PR should update this page with:

- completed next-wave item count,
- exact progress percentage,
- latest completed item,
- next recommended PR,
- validation commands,
- roadmap lane,
- KPI impact,
- rollback path.