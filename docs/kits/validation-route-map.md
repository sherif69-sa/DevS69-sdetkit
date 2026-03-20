# Validation route map

`sdetkit kits route-map` turns the repo's dependency and repo-usage signals into a searchable package-to-validation map.

Use it when you want a tighter answer than "run the whole suite":

> Which package or maintenance area changed, and what is the smallest safe command I should run next?

## Why it helps

The umbrella optimization and expansion surfaces already identify **validation route map** as one of the highest-leverage upgrades for the repo. This command makes that recommendation real by exposing:

- the package,
- its impact area,
- repo-usage tier,
- the primary validation command,
- alternate validation commands,
- source manifests and dependency groups,
- and the next maintenance action.

That helps with both **refactors** and **upgrade work** because the route map points you to the narrowest proof loop instead of a generic, expensive validation sweep.

## Example commands

```bash
python -m sdetkit kits route-map --format json
python -m sdetkit kits route-map httpx --repo-usage-tier hot-path --format json
python -m sdetkit kits route-map --impact-area runtime-core --limit 5
python -m sdetkit kits route-map topology --impact-area integration-adapters
```

## Typical workflow

1. Run `python -m sdetkit kits optimize --goal "upgrade umbrella architecture with agentos optimization"` to understand the repo-wide operating posture.
2. Run `python -m sdetkit kits route-map ...` to narrow the next validation lane for a package, impact area, or maintenance slice.
3. Run the `primary_validation` command for the best match first.
4. Escalate to alternate validation commands only when the smaller route shows risk.

## Good queries

- package names like `httpx`, `pytest`, or `mkdocs`
- impact-oriented terms like `runtime`, `quality`, or `docs`
- repo paths or surface words that show up in usage files

This makes the route map work well as both a maintenance lookup and a targeted search surface for repo upgrades.
