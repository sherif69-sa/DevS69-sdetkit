# Adaptive next-wave roadmap

The Adaptive Intelligence execution plan is complete. This next wave turns the completed adaptive foundation into deeper enterprise analytics, stronger remediation governance, and optional operator-facing product surfaces without weakening the review-first safety model.

## Continuation source bundle

Future roadmap updates must keep the work connected to the active prompt/source bundle, not only to chat memory.

### Active prompt files

- `DevS69_SDETKit_v11_ALIGNMENT_MANIFEST.md` — active file list, precedence, and product interpretation.
- `DevS69_SDETKit_MASTER_Prompt_v11_FULL_PRODUCT_RELEASE_ROADMAP.md` — full product-release roadmap and product north star.
- `DevS69_SDETKit_Continuation_Prompt_v11_POST_1829_PRODUCT_RELEASE.md` — restart checkpoint and next implementation slice.
- `DevS69_SDETKit_New_Chat_Startup_POST_1829.md` — new-chat startup and first verification checklist.
- `DevS69_SDETKit_FINAL_Master_Prompt_v10_0_POST_1829_PRODUCT_RELEASE_STRICT.md` — historical strict checkpoint retained for compatibility.
- `24_master_prompt.md` — active operating overlay for repo-native diagnosis, CI modeling, and reliability-platform direction.

### Supporting source files

Use these source files as the working checklist for future PRs:

- `00_index_and_usage.md`
- `01_repo_constitution.md`
- `02_cto_operating_model.md`
- `03_repo_reading_protocol.md`
- `04_change_classification_and_pr_cards.md`
- `05_green_main_and_baseline_gates.md`
- `06_naming_constitution.md`
- `07_naming_debt_burndown.md`
- `08_test_suite_professionalization.md`
- `09_docs_navigation_governance.md`
- `10_ci_workflow_governance.md`
- `11_dependency_hygiene.md`
- `12_release_and_supply_chain_governance.md`
- `13_security_posture.md`
- `14_feature_development_playbook.md`
- `15_refactor_and_migration_playbook.md`
- `16_failure_triage_playbook.md`
- `17_incident_response_and_recovery.md`
- `18_review_rubrics.md`
- `19_weekly_monthly_quarterly_cadence.md`
- `20_roadmap_and_kpi_system.md`
- `21_wsl2_command_book.md`
- `22_templates_library.md`
- `23_source_grounding_and_research_rules.md`
- `24_master_prompt.md`

### Continuation rule

Every future PR should state which prompt/source file it is using, which roadmap lane it advances, the expected validation commands, the rollback path, and the next recommended PR.

### Source role matrix

| Source area | Files | Future PR use |
| --- | --- | --- |
| Start and authority | `00_index_and_usage.md`, `01_repo_constitution.md`, `02_cto_operating_model.md`, `03_repo_reading_protocol.md` | Confirm the active source set, repo mission, stop rules, and required first read before work starts. |
| PR control | `04_change_classification_and_pr_cards.md`, `18_review_rubrics.md`, `22_templates_library.md` | Build the PR card, risk class, review verdict, rollback path, and next-step handoff. |
| Green-main and CI | `05_green_main_and_baseline_gates.md`, `10_ci_workflow_governance.md`, `16_failure_triage_playbook.md`, `17_incident_response_and_recovery.md` | Keep main green, diagnose failed gates, add first-failure artifacts, and recover safely from red CI. |
| Naming and architecture | `06_naming_constitution.md`, `07_naming_debt_burndown.md`, `15_refactor_and_migration_playbook.md` | Control naming, migrations, module splits, compatibility shims, and cleanup waves. |
| Tests and fixtures | `08_test_suite_professionalization.md`, `14_feature_development_playbook.md` | Require behavior-first tests, fixtures, regression coverage, and feature acceptance checks. |
| Docs and source grounding | `09_docs_navigation_governance.md`, `23_source_grounding_and_research_rules.md` | Keep docs discoverable, buildable, linked, and grounded in repo or cited sources. |
| Dependencies and release | `11_dependency_hygiene.md`, `12_release_and_supply_chain_governance.md` | Protect dependency truth, wheel/sdist quality, smoke installs, and release verification. |
| Security | `13_security_posture.md` | Guard workflow permissions, protected files, secret-like content, and security gates. |
| Cadence and KPIs | `19_weekly_monthly_quarterly_cadence.md`, `20_roadmap_and_kpi_system.md` | Keep roadmap progress, KPI targets, and action register current after each meaningful PR. |
| Local fallback | `21_wsl2_command_book.md` | Provide exact local commands when connector or CI evidence is insufficient. |
| Active overlay | `24_master_prompt.md` | Anchor diagnosis-first upgrades, control-plane ideas, verifier behavior, and reliability-platform direction. |

### Upgrade execution ladder

| Step | Upgrade slice | Primary source files | Definition of done |
| ---: | --- | --- | --- |
| 1 | Full-suite failure visibility | `10_ci_workflow_governance.md`, `16_failure_triage_playbook.md`, `05_green_main_and_baseline_gates.md` | Long pytest/coverage/matrix failures leave a concise artifact with first failure, traceback summary, environment, and reproduction command. |
| 2 | Merge-readiness monitor | `04_change_classification_and_pr_cards.md`, `05_green_main_and_baseline_gates.md`, `18_review_rubrics.md` | A local or CI artifact reports required checks as green, pending, failed, skipped, or action-required with the next owner action. |
| 3 | Package footprint guardrail | `12_release_and_supply_chain_governance.md`, `11_dependency_hygiene.md` | Wheel/sdist validation flags duplicate module content, unexpected helper files, missing package data, and public-surface drift before long CI. |
| 4 | Adoption provider parity | `14_feature_development_playbook.md`, `08_test_suite_professionalization.md`, `24_master_prompt.md` | GitHub Actions, GitLab CI, Jenkins, and local-script proof discovery follow the same read-only/review-first semantics. |
| 5 | Adoption fixture expansion | `08_test_suite_professionalization.md`, `14_feature_development_playbook.md` | Fixtures cover Python, JavaScript/TypeScript, Go, Rust, Java, .NET, docs, security, release, and mixed-CI repos. |
| 6 | Operator docs and repair playbooks | `09_docs_navigation_governance.md`, `16_failure_triage_playbook.md`, `21_wsl2_command_book.md` | Docs explain adoption discovery, review-first unknowns, PR repair, clean retriggers, and local fallback commands. |
| 7 | Roadmap-to-PR traceability | `20_roadmap_and_kpi_system.md`, `04_change_classification_and_pr_cards.md`, `22_templates_library.md` | PR bodies or templates always capture source file, lane, KPI impact, validation, rollback, and next PR. |

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
