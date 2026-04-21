# SDETKit architecture map (contributor quick guide)

This file is the shortest maintainer-oriented map of how the repo is organized so new contributors can quickly place changes in the right layer.

## 1) Stable first path (public contract)

The product's front door is intentionally narrow and stable:

1. `python -m sdetkit gate fast`
2. `python -m sdetkit gate release`
3. `python -m sdetkit doctor`

If your change can impact first-time adoption, validate this path first.

## 2) Command-surface tiers

- **Public / stable:** canonical release-confidence flows and their machine-readable artifact contracts.
- **Advanced but supported:** deeper operational lanes (`kits`, advanced review/gate/operator workflows).
- **Legacy / historical:** transition-era and hidden surfaces kept for compatibility and migration support.

Design intent: keep first-run confidence simple while preserving power surfaces for advanced operators.

## 3) Core runtime relationships

- `sdetkit.cli` is the root command router and entrypoint.
- `sdetkit.gate` orchestrates deterministic gate profiles and evidence output.
- `sdetkit.review` / `sdetkit.review_engine` provide unified review-state synthesis and operator-facing summaries.
- `sdetkit.doctor` gives remediation-oriented diagnostics and local environment checks.

## 4) Checks framework model (gate/review execution backbone)

The checks framework is profile-driven:

- check definitions and metadata
- planning and dependency ordering
- bounded execution and result collection
- stable artifact emission for CI/operator tooling

When changing checks behavior, prefer preserving schema and command-level contracts unless intentionally versioning them.

## 5) Plugin extension points

Plugins are discoverable via:

- Python entry points (packaging-time integrations)
- optional repository registry (`.sdetkit/plugins.toml`)

Plugin loading is resilience-first (skip failing plugins), with optional debug diagnostics to surface load failures when troubleshooting.

## 6) Legacy boundary policy

Legacy commands are supported for continuity but are not the preferred onboarding surface.

Contributor policy:

- avoid adding new features only to legacy lanes,
- route new capability through stable/advanced surfaces first,
- keep compatibility shims focused and observable.

## 7) Where to read next

- Product/usage front door: `README.md`
- Stability policy: `docs/stability-levels.md`
- CLI details: `docs/cli.md`
- Docs hub: `docs/index.md`
