# Upgrade implementation research and recommendations

This document summarizes practical upgrade methods for SDETKit with a focus on:

1. compatibility risk management,
2. measurable performance improvements, and
3. low-friction workflow changes.

The baseline inventory came from the repository's direct dependency audit command (`make upgrade-audit`).

## 1) Current baseline and where risk concentrates

### Runtime and tooling baseline

- Python support is `>=3.11` with CI lanes on 3.11 and 3.12.
- Runtime direct dependency surface is intentionally small (`httpx`).
- Most pinned dependencies are in `dev`, `docs`, and `packaging` extras.

### Upgrade hotspots identified

- **Test stack is unbounded** (`pytest`, `pytest-asyncio`, `pytest-cov`, `hypothesis`) and currently resolves to latest major versions.
- **Integration adapters are bounded but broad** (`python-telegram-bot>=21,<23`, `twilio>=9,<10`) and should be upgraded with adapter contract checks.
- **Operational quality gates are mature** (`quality.sh`, CI matrix, package validate), so upgrades can safely be staged through existing lanes.

## 2) Most effective method: staged "observe → constrain → upgrade → unfreeze"

### Phase A — Observe (now)

1. Capture a machine-readable baseline before changes:
   - `make upgrade-audit`
   - `python -m pip freeze > build/upgrade-baseline-freeze.txt`
2. Record current gate performance (duration + pass/fail):
   - `bash ci.sh quick --skip-docs --artifact-dir build`
   - `bash quality.sh cov` (or CI lane equivalent with 95% threshold)

**Why this works:** it gives a deterministic "before" state for both dependency graph and execution performance.

### Phase B — Constrain (short-term hardening)

1. Add upper bounds to currently-unbounded test dependencies.
2. Introduce a constraints file for CI reproducibility (for example `constraints-ci.txt`) while keeping `pyproject.toml` flexible enough for ecosystem compatibility.
3. Keep runtime dependencies minimally bounded (current strategy is already good).

**Why this works:** prevents accidental major-version adoption during unrelated PRs while preserving controlled upgrade windows.

### Phase C — Upgrade (batch by risk domain)

Run upgrades in small batches with dedicated validation scopes:

1. **Batch 1: test tooling only** (`pytest*`, `hypothesis`)
   - Validate with fast + full test/cov lanes.
2. **Batch 2: docs + packaging tooling** (`mkdocs*`, `build`, `twine`, `check-wheel-contents`)
   - Validate docs build + package-validate + smoke install matrix.
3. **Batch 3: integration adapters** (`python-telegram-bot`, `twilio`)
   - Validate adapter CLI paths and plugin entrypoint behavior.
4. **Batch 4: runtime dependency changes** (`httpx` major/minor only when needed)
   - Validate API client contracts, retries, and async paths.

**Why this works:** isolates blast radius, shortens rollback decisions, and keeps CI signal actionable.

### Phase D — Unfreeze

After each batch is stable:

1. Update compatibility notes/changelog.
2. Remove temporary hotfix pins introduced only for transition.
3. Keep new/updated regression tests that caught real breakages.

## 3) Compatibility strategy recommendations

### A. Contract-first gating

For each upgrade batch, require contract checks for:

- CLI output schema stability for key commands.
- Plugin entrypoint loading for optional adapters.
- Artifact envelope compatibility (`--format json` outputs used by CI/reports).

### B. Explicit support lanes

Maintain these support expectations:

- Python 3.11 and 3.12 parity for release-critical commands.
- Offline-default test behavior remains intact (`pytest -m 'not network'`).
- Existing compatibility command lanes remain functional during umbrella-kit migration.

### C. Rollback safety

- Every batch should have one "revert-only" PR path (dependency pin rollback, no code semantics change).
- Keep a short-lived upgrade branch per batch until green on full CI + smoke install matrix.

## 4) Performance improvement opportunities during upgrade

### A. Dependency and install performance

- Use constraints and lock snapshots in CI to reduce resolver churn.
- Keep extras split by concern (`dev`, `test`, `docs`, `packaging`) to avoid over-installing on fast lanes.

### B. Execution performance

- Keep the existing fast lane as primary PR gate (`ci.sh quick --skip-docs`).
- Track median duration for:
  - fast lane,
  - coverage lane,
  - package validate + smoke install.
- Only promote additional checks to blocking status when they show low flake and stable runtime.

### C. Network-sensitive surfaces

- For adapter upgrades, keep network tests opt-in and preserve offline defaults.
- Add deterministic fixtures/cassettes when upgrade introduces API behavior shifts.

## 5) Workflow adjustments recommended for this repo

1. **Add a recurring upgrade cadence**
   - Weekly: audit-only report (`make upgrade-audit`) and candidate shortlist.
   - Bi-weekly: one low-risk batch PR.
   - Monthly: one medium-risk batch (adapters/runtime only if required).

2. **Introduce a lightweight upgrade PR template**
   - sections: scope, risk level, compatibility impact, rollback plan, CI evidence.

3. **Capture upgrade evidence artifacts**
   - store before/after outputs under `build/` in CI artifacts for timing + behavior comparisons.

4. **Keep release preflight as final guardrail**
   - Require `make release-preflight` before tagging any release that includes dependency shifts.

## 6) Suggested immediate next steps

1. Add bounded ranges for unpinned test dependencies.
2. Add a CI constraints file and install it in fast/full workflows.
3. Run first low-risk upgrade batch (test tooling only).
4. Review performance delta from CI artifacts before moving to adapter/runtime upgrades.

---

If we follow this phased method, upgrades remain predictable, reversible, and evidence-driven while preserving SDETKit's current compatibility promises.
