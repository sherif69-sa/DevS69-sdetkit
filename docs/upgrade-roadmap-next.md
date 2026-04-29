# Next Upgrade Plan (Practical, High-Impact)

This roadmap is designed to help the team continue upgrades in a focused way, without losing the deterministic ship/no-ship core.

## What is already strong

- Clear canonical workflow (`gate fast` -> `gate release` -> `doctor`) and a concrete first-proof entrypoint.
- Strong artifact-driven model (`build/first-proof/*`) that supports auditable decisions.
- Broad operational scripting footprint for governance, reporting, and closeout checks.

## Where the next upgrades should go

## Upgrade 1: Reduce command/entrypoint complexity

**Problem:** There are many scripts and make targets; discovery cost is high for new operators.

**Next actions:**
- Add a single `make upgrade-next` target that prints and optionally runs a curated "next 5 commands" path.
- Add one docs page that maps frequent intents ("I need release confidence", "I need weekly ops", "I need remediation") to exact commands.
- Mark legacy or low-frequency paths as advanced-only in docs.

**Success metric:** time-to-first-success for a new contributor < 15 minutes.

## Upgrade 2: Add a "health score" rollup for executive visibility

**Problem:** There are many artifacts, but leadership may need one quick readiness score + trend.

**Next actions:**
- Create a tiny score contract (0-100) derived from gate status, doctor status, failing contracts, and trend stability.
- Emit `build/first-proof/health-score.json` and `health-score.md`.
- Include the score in PR/CI summaries.

**Success metric:** one-line readiness signal visible in CI + weekly reports.

## Upgrade 3: Tighten failing-check remediation guidance

**Problem:** Failing contracts are deterministic, but guidance may still require manual interpretation.

**Next actions:**
- Standardize a remediation hint block for each `check_*` script (`why`, `likely causes`, `first fix step`).
- Add a `make doctor-remediate` helper to route users to the top 3 blockers with commands.

**Success metric:** median time-to-fix for top recurrent failures reduced by 30%.

## Upgrade 4: Stabilize release evidence lifecycle

**Problem:** Artifact freshness and retention policy can drift over time.

**Next actions:**
- Define retention windows for first-proof and maintenance artifacts.
- Add one automated check that flags stale evidence in CI.
- Add a versioned schema reference for key output artifacts.

**Success metric:** no ambiguous/stale artifact usage in release decisions.

## Upgrade 5: Strengthen "adoption by default"

**Problem:** Great system depth, but adoption can lag without opinionated defaults.

**Next actions:**
- Add one bootstrap command that sets up environment + runs first-proof verification end-to-end.
- Publish a 7-day "operator onboarding" checklist using existing commands.
- Add a compact dashboard in docs linking first-proof, weekly trend, and maintenance command center.

**Success metric:** new team can run full baseline flow by day 1.

## 30/60/90-day execution split

### First 30 days
- Implement Upgrade 1 and Upgrade 2 as the highest leverage for clarity and visibility.
- Ship docs simplification and health-score artifacts.

### Days 31-60
- Implement Upgrade 3 remediation assistant and top-failure guidance blocks.
- Track failure recurrence and time-to-fix.

### Days 61-90
- Implement Upgrade 4 and 5 hardening/adoption improvements.
- Finalize retention/schema checks and onboarding dashboard.

## Suggested immediate "next three" tasks

1. Add `make upgrade-next` + command-intent docs page.
2. Add `health-score.json` generator and include it in first-proof pipeline.
3. Add `make doctor-remediate` for top deterministic blockers.
