# Archive navigation policy

This policy explains how SDETKit handles documentation that is built by MkDocs but intentionally not promoted into the primary navigation.

The goal is to keep the public documentation useful for active operators while still preserving older reports, closeout notes, implementation plans, and supporting material. A page being outside `nav` is not automatically a defect. It means the page needs one of three clear outcomes:

1. promote it into primary navigation,
2. group it under an archive or supporting-reference section,
3. leave it outside navigation because it is generated, timebound, or transitional evidence.

## Why this policy exists

The documentation set contains both product documentation and operating history. Those are different reader experiences.

Product documentation should help a user install, run, adopt, verify, integrate, and operate SDETKit. Those pages belong in the active navigation.

Operating history captures the work that produced the toolkit. That includes upgrade reports, dated execution plans, closeout records, investor-readiness snapshots, roadmap artifacts, and one-off follow-up trackers. Those pages can remain valuable, but they should not crowd the active reader journey.

The MkDocs inventory warning is therefore treated as a triage signal, not a blanket order to add every Markdown file to the nav.

This policy is not historical reports promotion; it is archive triage for stable navigation.

## Navigation tiers

SDETKit uses four practical documentation tiers.

### Tier 1: primary journey docs

Primary journey docs belong in the main nav when they are current, maintained, and directly useful to a new or returning operator.

Examples include:

- install and quickstart pages
- first-proof guidance
- adoption and rollout guidance
- release-confidence guidance
- operator evidence guidance
- active CLI, API, and command references
- integration reference packs
- compatibility and contract pages

A Tier 1 page should answer an active user question without requiring historical context.

### Tier 2: current supporting references

Supporting references may belong in nav when they define current contracts, policies, compatibility rules, or operational expectations.

Examples include:

- command contracts
- CI status bridge docs
- environment compatibility docs
- docs cleanup progress docs
- integration examples
- active policy records
- current troubleshooting pages

These pages may be secondary, but they still support an active operating decision.

### Tier 3: archive candidates

Archive candidates are valid docs that should usually not be mixed into the primary journey.

Examples include:

- dated upgrade reports
- execution plans tied to a specific date
- cycle closeout reports
- investor-readiness snapshots
- historical audit records
- one-off follow-up trackers
- generated roadmap artifact packs
- old productization notes that are preserved for traceability

Archive candidates need a separate archive strategy before nav promotion.

### Tier 4: generated or intentionally excluded material

Some docs are intentionally excluded from nav or excluded from the built site.

Examples include:

- generated sample outputs
- raw artifact folders
- automation template internals
- generated weekly packs
- machine-produced report fragments

These should not be promoted into nav unless a human-facing index page is created.

## Promotion rules

A page may be promoted from the inventory into `nav` when all of these are true:

- it serves an active user journey,
- its title is stable enough to appear in public navigation,
- it does not duplicate a better canonical page,
- it is not merely a dated report or historical snapshot,
- it has enough context to be useful when opened directly,
- it belongs near an existing section without confusing the nav hierarchy.

Promotion should be done in cohesive slices, not one-off additions.

Good slices include:

- first-proof and adoption docs,
- operator evidence docs,
- integration reference docs,
- release room and readiness docs,
- support and escalation docs,
- archive index docs.

Poor slices include:

- one random report,
- one generated artifact,
- every remaining Markdown file,
- a mix of unrelated old plans and current references,
- dated closeout records added to the primary journey.

## Archive rules

A page should stay outside primary navigation when it is mostly historical or timebound.

Common archive markers include:

- a date in the file name or title,
- a cycle number in the file name or title,
- report or closeout language,
- investor or audit snapshot language,
- plan-execution follow-up language,
- generated weekly-pack paths,
- roadmap artifact paths.

Archive pages can still be linked from an archive index, a roadmap index, or a cleanup progress page.

The preferred pattern is to create a curated index before adding many archive pages to nav.

## Current examples of archive candidates

The following groups are examples of pages that should not be blindly promoted into primary navigation:

### Continuous upgrade closeout reports

Files like `continuous-upgrade-big-upgrade-report-1.md` through later cycle reports are historical closeout material. They may be useful for traceability, but they should live behind an archive or upgrade-history index.

### Dated execution plans

Files such as `powerfuel-execution-plan-2026-05-03.md` and `plan-execution-followup-2026-04-23.md` are dated operating records. They should not appear beside stable operator docs unless curated into a historical execution archive.

### Investor and readiness snapshots

Files like `investor-readiness-review-2026-04-18.md` and `enterprise-readiness-audit-2026-04.md` are timebound evidence snapshots. They are not primary docs for everyday users.

### Roadmap artifact packs

Files under `roadmap/artifacts/weekly-pack-*` are generated or package-like supporting artifacts. They should be linked from a roadmap archive or release pack index rather than added one by one.

### Productization history

Docs such as `enterprise-productization-blueprint.md`, `final-enterprise-reliability-plan.md`, and older program dashboards may still matter, but they need curation before primary nav placement.

## Active-reference examples

Some pages may look secondary but should be considered current-reference candidates.

Examples include:

- support and escalation guidance,
- environment compatibility guidance,
- release readiness guidance,
- workflow consolidation maps,
- security suite guidance,
- policy and baseline guidance,
- compatibility and deprecation policy.

These should be promoted only in a coherent slice with tests.

## Test expectations

Navigation policy tests should avoid checking that every Markdown file is in nav.

Instead, tests should check that:

- active slices that were intentionally promoted stay in nav,
- archive-policy docs are present and discoverable,
- known archive examples remain classified as archive candidates,
- generated or timebound material is not accidentally treated as primary navigation,
- MkDocs config is parsed safely without unsafe YAML loading.

The test contract should protect intent without freezing the entire inventory forever.

## Pull request sizing

Navigation cleanup PRs should be large enough to be worth review.

For this repository, do not push tiny nav-only fixes. A navigation governance PR should generally include:

- a coherent policy or cleanup slice,
- a regression test,
- proof that the slice stays out of the inventory warning,
- at least 260 added lines unless the change is an urgent CI repair.

This keeps documentation work reviewable and avoids noisy micro PRs.

## Review checklist

Before opening a docs navigation PR, verify:

- `mkdocs.yml` is valid YAML,
- page titles with colons are quoted,
- new docs are ASCII-safe unless there is a deliberate exception,
- tests avoid `yaml.load`,
- MkDocs strict build passes,
- pre-commit passes,
- fast CI gate passes,
- added-line count meets the branch size bar,
- the PR body explains why the slice belongs together.

## Merge guidance

Merge navigation cleanup only when the hard gates are green.

Bot comments from adaptive diagnosis may be advisory when lint, tests, coverage, and required checks are green. Unknown adaptive diagnoses should be reviewed, but they should not be treated as automatic blockers unless they point to a concrete failing gate.

## Future cleanup lanes

Recommended future lanes:

1. release readiness and release room docs,
2. support and escalation docs,
3. security and policy docs,
4. archive index for dated reports,
5. roadmap archive index,
6. generated artifact reference cleanup.

Each lane should be its own PR with a clear title, proof commands, and a guardrail test when behavior can regress.
