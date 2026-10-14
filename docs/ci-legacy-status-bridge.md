# Legacy required status bridge (`ci`)

## What is this line?

If your PR checks show an entry like:

- `ci — Legacy required status bridge: CI workflow passed.`

that is a **compatibility status context** published by `.github/workflows/legacy-required-status-bridge.yml`.

It mirrors the real `CI` workflow result into the `ci` context that branch protection requires. On a new pull request it is `pending` until the `CI` workflow completes, then it becomes `success` or `failure` to match that workflow.

## What about `maintenance-autopilot`?

The required `maintenance-autopilot` context is reported by the real job in `.github/workflows/maintenance-autopilot.yml` (job name `maintenance-autopilot`). The bridge never publishes it, so it only turns green when the autopilot actually ran and passed.

## What should I do as a maintainer?

Usually: **nothing**. If `CI` and `maintenance-autopilot` are green, the required contexts are satisfied.

## When should I investigate?

Investigate only if one of these happens:

1. `ci` stays pending after the `CI` workflow finished.
2. `legacy-required-status-bridge / publish-legacy-statuses-from-ci-workflow` failed.
3. `maintenance-autopilot` failed: open that job's logs and its uploaded `maintenance-autopilot` artifact.

## How to interact (if needed)

1. Re-run `legacy-required-status-bridge / publish-legacy-statuses-from-ci-workflow` from the Checks tab.
2. If still stuck, verify branch protection required contexts include `ci` and `maintenance-autopilot`.
3. Optional long-term cleanup: require the modern `CI` job contexts directly and remove the bridge.
