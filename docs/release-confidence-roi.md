# Release confidence ROI (without invented metrics)

This page describes practical value teams can capture from SDETKit without using fabricated percentages or synthetic customer claims.

## What value looks like in practice

## 1) Fewer ad hoc release decisions

Teams use a declared command path (`gate fast` → `gate release` → `doctor`) and consistent artifact fields (`ok`, `failed_steps`) to decide whether to advance a change.

That reduces “it depends who reviewed it” decision patterns and creates a shared decision language.

## 2) Less time spent reading raw logs

Instead of starting with full log streams, teams begin with structured artifacts:

- `build/release-preflight.json` for top-level go/no-go context
- `build/gate-fast.json` for focused failure breakdown

Raw logs are still available, but they become a second-step drill-down, not the first triage surface.

## 3) One repeatable local-to-CI path

The same commands can run on a laptop and in CI, with the same artifact contract. That reduces friction when reproducing issues between local development, PR validation, and release checks.

## 4) Machine-readable evidence for repeatable reviews

JSON outputs allow deterministic review workflows:
- reviewers can inspect the same fields every time
- automation can parse artifacts without brittle text scraping
- release records can store evidence in a stable structure

## 5) Better handoff across roles

SDETKit artifacts support cleaner handoff between:
- engineers preparing a change
- reviewers validating readiness
- release owners making advancement calls

Each role sees the same structured decision inputs, which lowers ambiguity in review and sign-off conversations.

## Adoption note

ROI should be validated by each team against its own baseline (current review time, release friction, and defect escape profile). SDETKit provides a repeatable evidence path; teams should measure the impact in their own delivery context.
