# Legacy required status bridge (`ci`, `maintenance-autopilot`)

## What are these lines?

If your PR checks show entries like:

- `ci — Legacy required status bridge: see modern workflow checks for detailed signal.`
- `maintenance-autopilot — Legacy required status bridge: see modern workflow checks for detailed signal.`

those are **compatibility status contexts** published by `.github/workflows/legacy-required-status-bridge.yml`.

They exist only to satisfy older branch-protection requirements that still expect legacy context names.

## Are these real checks?

They are **status shims** (bridge statuses), not the main source of truth.

Use the modern workflow checks for real health signals, for example:

- `CI / Full CI lane (pull_request)`
- `legacy-required-status-bridge / publish-legacy-statuses (pull_request)`
- Other repository quality/security checks

## What should I do as a maintainer?

Usually: **nothing**. If your PR is mergeable and all modern checks are green, this is expected.

## When should I investigate?

Investigate only if one of these happens:

1. `ci` or `maintenance-autopilot` stays pending for too long.
2. `legacy-required-status-bridge / publish-legacy-statuses` failed.
3. Branch protection blocks merge while modern checks are green.

## How to interact (if needed)

1. Re-run `legacy-required-status-bridge / publish-legacy-statuses` from the Checks tab.
2. If still stuck, verify branch protection required contexts include `ci` and `maintenance-autopilot`.
3. Optional long-term cleanup: migrate branch protection to modern contexts and then remove bridge contexts.
