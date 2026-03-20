# Expansion lab

`sdetkit kits expand --goal "..."` is the repo-growth surface for SDETKit's umbrella architecture.

Use it when the repo is already healthy enough to optimize, but you want the tool to answer a harder question:

> What should we add next to make the repo better, more productized, and easier to evolve?

## What it emits

The expand payload builds on top of `sdetkit kits optimize --goal "..."` and turns alignment signals into three implementation-friendly sections:

- **feature candidates** — concrete additions with priority, effort, deliverables, and commands,
- **search missions** — focused research directions for follow-up discovery,
- **rollout tracks** — a now / next / later sequence for turning ideas into a controlled roadmap.

## Example

```bash
python -m sdetkit kits expand --goal "upgrade umbrella architecture with agentos optimization"
python -m sdetkit kits expand --goal "upgrade umbrella architecture with agentos optimization" --format json
```

## Typical output themes

Depending on the repo signals and dependency inventory, the expansion lab can suggest additions such as:

- a **dependency radar dashboard** for recurring upgrade visibility,
- a **validation route map** that links packages to the smallest safe proof loop,
- an **adapter smoke pack** that makes optional integrations feel productized,
- a **runtime fast-follow watchlist** for hot-path dependencies,
- or an **optimization control center** that collapses boost + AgentOS outputs into one recurring operating view.

The validation route map is now available directly via `sdetkit kits route-map`, so one strong follow-up pattern is:

```bash
python -m sdetkit kits expand --goal "upgrade umbrella architecture with agentos optimization"
python -m sdetkit kits radar --repo-usage-tier hot-path --format json
python -m sdetkit kits route-map --impact-area runtime-core --limit 5
```

## How to use it well

1. Run `sdetkit kits optimize --goal "..."` first if you need the full alignment payload.
2. Run `sdetkit kits expand --goal "..."` when you want the next additions, not just the current posture.
3. Take the `now` rollout track and ship one candidate end to end before widening the backlog.

That pattern keeps repo growth deliberate instead of turning "more features" into scattered churn.
