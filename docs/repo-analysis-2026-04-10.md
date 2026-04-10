# Repository Analysis — April 10, 2026

## Scope

This report summarizes a quick health and structure analysis of the repository, focused on:

- project layout and scale,
- packaging/tooling posture,
- current test/lint status,
- immediate risks visible from failing checks.

## What was inspected

- `README.md`
- `pyproject.toml`
- `quality.sh`
- `docs/index.md`
- `src/sdetkit/cli.py`

## High-level findings

1. **Clear product direction and first-run path.**
   The README strongly centers the release-confidence flow and artifact-first troubleshooting path.

2. **Large, mature surface area.**
   The repository currently contains:
   - ~3,596 Python files,
   - 278 test files,
   - 684 docs markdown files.

3. **Quality baseline is mostly healthy.**
   - `ruff check src tests` passes.
   - Full pytest run is high-pass but not green (4 failures / 1,569 passing, 3 deselected).

4. **Current failures are mostly contract drift, not runtime crashes.**
   The failing tests point to content/expectation mismatches:
   - hidden-command/help text policy around the word `proof`,
   - docs navigation strict contract expectations,
   - quality script usage string mismatch.

## Failing areas from test run

### 1) CLI help surface contract drift

Two tests fail because they expect `proof` to not appear in root help output, but `proof` appears in description text (e.g., “canonical first proof path”).

Likely cause:
- tests currently enforce a very strict string-level constraint,
- help prose changed in a way that includes the token while command hiding still exists.

### 2) Docs navigation strict mode mismatch

`docs-navigation` strict test reports missing required sections/anchors in `docs/index.md`, including quick-jump wrapper and legacy reports links.

Likely cause:
- docs governance checks were tightened or defaults changed,
- `docs/index.md` structure did not get updated to satisfy the current strict contract.

### 3) `quality.sh` usage text mismatch

A test expects a usage line without `brutal`, but script now documents `brutal` mode.

Likely cause:
- script behavior evolved,
- test assertion string was not updated.

## Suggested next actions

1. **Resolve contract intent first (policy decision):**
   Decide whether tests should enforce literal token exclusion (`proof`) in all help text, or only exclude it as a command listing.

2. **Align docs governance contract:**
   Either:
   - restore expected quick-jump/legacy/top-journeys sections in `docs/index.md`, or
   - intentionally update `docs_navigation` expected defaults/tests if governance rules changed.

3. **Synchronize `quality.sh` and tests:**
   Update test expectation to include `brutal` mode, or remove `brutal` from usage/help if it should not be public.

4. **Add a “contract drift” CI lane (optional):**
   A focused test subset around CLI help, docs-nav, and quality script contracts can fail fast before full-suite runtime.

## Commands run

- `python --version`
- `pytest -q`
- `ruff check src tests`
- `python - <<'PY' ...` (counts for Python files, test files, docs markdown)

## Current status snapshot

- Lint: pass
- Test suite: mostly pass, 4 targeted failures
- Risk level: **low-to-moderate** (contract drift with high visibility, low core runtime risk based on this pass)
