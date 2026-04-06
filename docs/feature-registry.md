# Feature registry

The feature registry keeps SDETKit broad **and** useful by making each command explicitly accountable to user value.

## Why this exists

As the command surface grows, users need a deterministic way to know which commands are core, advanced, and experimental.

The registry adds a lightweight contract per command:

- Tier (`A`, `B`, `C`)
- Stability status (`stable`, `advanced`, `experimental`)
- Problem solved
- Copy-paste example
- Expected output summary
- Linked test file
- Linked docs page

## Tier model

- **Tier A**: core/default commands that should be trusted first by most users.
- **Tier B**: advanced commands that are valuable but situational.
- **Tier C**: experimental/lab commands where iteration speed matters more than API stability.

## Registry table (auto-generated)

The table below is generated from `src/sdetkit/data/feature_registry.json`.
Run `python scripts/sync_feature_registry_docs.py` after registry updates.

<!-- feature-registry:table:start -->
| Command | Tier | Status | Problem solved | Example | Test | Docs |
| --- | --- | --- | --- | --- | --- | --- |
| `doctor` | A | stable | Provides deterministic repo diagnostics and readiness scoring. | `python -m sdetkit doctor --format md` | `tests/test_cli_doctor.py` | [docs/doctor.md](doctor.md) |
| `forensics` | A | stable | Compares runs and pinpoints failure deltas for root-cause analysis. | `python -m sdetkit forensics compare --from examples/kits/forensics/run-a.json --to examples/kits/forensics/run-b.json` | `tests/test_cli_sdetkit.py` | [docs/cli.md](cli.md) |
| `gate` | A | stable | Runs fast and strict confidence checks for release control. | `python -m sdetkit gate fast` | `tests/test_gate_fast.py` | [docs/cli.md](cli.md) |
| `integration` | A | stable | Validates integration topologies and runtime compatibility. | `python -m sdetkit integration check --profile examples/kits/integration/profile.json` | `tests/test_integration_feedback_closeout.py` | [docs/cli.md](cli.md) |
| `intelligence` | A | stable | Analyzes failure trends and flaky behavior for triage. | `python -m sdetkit intelligence --help` | `tests/test_cli_sdetkit.py` | [docs/cli.md](cli.md) |
| `kits` | A | stable | Discovers the curated umbrella surfaces for fast adoption. | `python -m sdetkit kits list` | `tests/test_cli_sdetkit.py` | [docs/cli.md](cli.md) |
| `release` | A | stable | Runs release-confidence checks and gate workflows. | `python -m sdetkit release gate fast` | `tests/test_release_readiness.py` | [docs/release-readiness.md](release-readiness.md) |
| `repo` | A | stable | Performs repo policy and automation audits. | `python -m sdetkit repo --help` | `tests/test_repo_check_cli.py` | [docs/repo-audit.md](repo-audit.md) |
<!-- feature-registry:table:end -->

## Source of truth

Registry data file: `src/sdetkit/data/feature_registry.json`

Loader module: `src/sdetkit/feature_registry.py`

Validation test: `tests/test_feature_registry.py`

CI contract command: `python scripts/check_feature_registry_contract.py`

Docs sync command: `python scripts/sync_feature_registry_docs.py --check`

CLI inspection command: `python -m sdetkit feature-registry --only-core --format table`

Markdown export command: `python -m sdetkit feature-registry --format markdown`

Maintenance lane command: `bash quality.sh registry`

Summary command: `python -m sdetkit feature-registry --format summary-json`

Assertion command (CI-safe): `python -m sdetkit feature-registry --only-core --expect-command kits --expect-command release --expect-total 8 --expect-tier-count A=8 --expect-status-count stable=8 --fail-on-empty --format summary-json`

## Expected operating flow

1. Add or update command in the registry.
2. Link a test and docs page.
3. Keep tier and stability current as command maturity changes.
4. Use the registry as input for future CLI grouping and docs generation.
