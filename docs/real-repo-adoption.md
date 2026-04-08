# Real repo adoption proof (canonical fixture)

This is the **flagship trust lane** for repo adoption proof.

A skeptical maintainer should only need this one path to verify:
- what commands ran,
- what artifacts were produced,
- what passed vs failed,
- why those outcomes are trustworthy,
- and how local evidence maps to CI evidence.

## Canonical fixture

Path: `examples/adoption/real-repo/`

Fixture shape (intentionally small, repo-realistic):
- `pyproject.toml`
- `src/app/__init__.py`
- `src/app/main.py`
- `tests/test_main.py`

## Canonical local replay (exact commands)

From repo root:

```bash
python -m pip install -e .
cd examples/adoption/real-repo
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json ; echo $? > build/gate-fast.rc
python -m sdetkit gate release --format json --out build/release-preflight.json ; echo $? > build/release-preflight.rc
python -m sdetkit doctor --format json --out build/doctor.json ; echo $? > build/doctor.rc
python ../../../scripts/real_repo_adoption_projection.py --fixture-root . --repo-root ../../.. --build-dir build --out build/adoption-proof-summary.json
```

## Canonical artifacts (single evidence pack)

Both local replay and CI replay produce the same canonical files:
- `build/gate-fast.json`
- `build/release-preflight.json`
- `build/doctor.json`
- `build/gate-fast.rc`
- `build/release-preflight.rc`
- `build/doctor.rc`
- `build/adoption-proof-summary.json`

Checked-in golden references live at `artifacts/adoption/real-repo-golden/` with the same filenames.

## Truthful expected outcomes (not theatrical)

For this fixture, intentional first-run triage behavior is part of the trust signal:

| Command | Expected `rc` | Expected artifact `ok` | Why trustworthy |
| --- | --- | --- | --- |
| `gate fast` | `2` | `false` | Fails on missing full-repo policy/test wiring; this is realistic first-run adoption triage. |
| `gate release` | `2` | `false` | Depends on release doctor + fast gate; failure mirrors realistic preflight gating. |
| `doctor` | `0` | `true` | Produces actionable quality checks while command execution still succeeds. |

Use `build/adoption-proof-summary.json` as the canonical decoder: it records command, artifact contract projection, observed rc/ok, expected rc/ok, and expectation-match booleans.

## CI mirror (same story as local)

Workflow: `.github/workflows/adoption-real-repo-canonical.yml`

CI does three things in this exact order:
1. `python scripts/regenerate_real_repo_adoption_goldens.py --check` (drift guard)
2. replay canonical fixture commands and rc capture
3. upload canonical artifacts as `adoption-real-repo-canonical`

No separate CI-only evidence format is used; CI uploads the same artifact names as local replay.

## Golden freshness and drift guard

Check only (no rewrites):

```bash
python scripts/regenerate_real_repo_adoption_goldens.py --check
```

Refresh intentionally (after fixture or gate-contract changes):

```bash
python scripts/regenerate_real_repo_adoption_goldens.py
```

The helper regenerates fixture artifacts, rc files, and the proof summary, then compares projected contracts so path-specific volatility does not create false drift.
