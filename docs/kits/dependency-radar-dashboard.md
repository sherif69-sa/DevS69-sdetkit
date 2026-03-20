# Dependency radar dashboard

`sdetkit kits radar` turns the repo's upgrade inventory into a dashboard-friendly maintenance view.

Use it when you want more than a raw dependency report and need a sharper answer to:

> Which dependency areas are hottest right now, and what should we validate first?

## What it emits

The radar payload builds on the manifest-aware upgrade inventory and the validation route map, then adds:

- **headline metrics** for the maintenance surface,
- **dashboard cards** for hot-path, runtime-core, and quality-tooling watchlists,
- **hotspots** that expose the strongest package-to-validation routes,
- **watchlists** for recurring review slices,
- and **maintenance lanes** that suggest what to run next.

That makes it easier to move from “we should probably upgrade things” to a concrete operating review with smaller proof loops.

## Example commands

```bash
python -m sdetkit kits radar --format json
python -m sdetkit kits radar httpx --repo-usage-tier hot-path --format json
python -m sdetkit kits radar --impact-area runtime-core --limit 5
python -m sdetkit kits radar docs --impact-area quality-tooling
```

## Typical workflow

1. Run `python -m sdetkit kits optimize --goal "upgrade umbrella architecture with agentos optimization"` to understand the umbrella posture.
2. Run `python -m sdetkit kits radar ...` to turn the upgrade surface into a review-ready dashboard.
3. Use the **hotspots** section to pick the first package-specific validation loop.
4. Use the **maintenance lanes** section to schedule recurring review or AgentOS export.

## Why this is useful

The expansion lab already identified a **dependency radar dashboard** as one of the best next additions for the repo. This command productizes that idea directly, so the upgrade conversation becomes:

- visible,
- prioritized,
- and tied to specific validation commands rather than broad maintenance intuition.
