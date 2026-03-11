# Release confidence with SDETKit

SDETKit exists for one primary outcome: help teams make a release decision with deterministic checks and audit-friendly evidence.

## Core idea

Use one repeatable command path to answer:

**"Is this repository ready to ship?"**

## Why this instead of separate tools

Many teams already run linting, tests, and scanners. The gap is usually release decision clarity.

SDETKit focuses that gap by combining:

- deterministic gate commands with stable exit behavior
- strict release policies (`gate release`, security budgets)
- evidence-oriented outputs for post-run review

This turns scattered checks into a consistent go/no-go workflow.

## The core path

For new users and adopters, use this sequence:

1. **Quick confidence**

   ```bash
   bash scripts/ready_to_use.sh quick
   ```

2. **Strict release gate**

   ```bash
   bash scripts/ready_to_use.sh release
   ```

3. **Adopt in external repository**

   Follow [adoption.md](adoption.md) for copy-paste rollout in CI and local workflows.

## Who gets the most value

- SDET/QA teams needing deterministic pass/fail gates
- Platform/DevOps teams enforcing policy-aware release checks in CI
- Maintainers who need audit-friendly artifacts for release review

## Start here

- Quickstart: [ready-to-use.md](ready-to-use.md)
- External rollout: [adoption.md](adoption.md)
- First-failure triage: [adoption-troubleshooting.md](adoption-troubleshooting.md)
- Practical scenarios: [examples.md](examples.md)
