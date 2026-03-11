# Remediation cookbook (first-failure playbooks)

Use this page after your **first failed SDETKit command** in an external repository.

It is intentionally compact: identify the failed step, run the safest next command, fix one class of issue, rerun.

If you came from a downloaded GitHub Actions artifact, first map file -> next section in [Adoption troubleshooting](adoption-troubleshooting.md#artifact-to-action-map-open-this-first-after-download), then use the matching playbook here.

## 0) Start with machine-readable failure output

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
cat build/gate-fast.json
```

Why: `failed_steps` tells you exactly which playbook to use next.

---

## 1) `gate fast` failed on `ruff`

**What failed**

`gate fast: FAIL` and `failed_steps` includes `ruff` or `ruff_format`.

**Likely meaning**

Your repo has lint and/or formatting debt. This is common on first adoption.

**Safest next commands**

```bash
# inspect only
python -m ruff check .
python -m ruff format --check .

# optional minimal auto-fix pass
python -m sdetkit gate fast --only ruff,ruff_format --fix
```

**Smallest fix path**

1. Run `ruff check` to see exact rule IDs/files.
2. Apply small fixes (or scoped `--fix`) and review the diff.
3. Rerun `python -m sdetkit gate fast`.

**Stay lightweight vs tighten later**

- Lightweight now: keep `gate fast` as the PR gate while you reduce lint debt.
- Tighten later: move to release gating only after `gate fast` is consistently green.

---

## 2) `gate fast` failed on `mypy`

**What failed**

`gate fast: FAIL` and `failed_steps` includes `mypy`.

**Likely meaning**

Type errors were found in the checked target (default: `src`).

**Safest next commands**

```bash
# rerun exactly what gate fast runs by default
python -m mypy src

# narrow while adopting (example)
python -m sdetkit gate fast --only mypy --mypy-args "src/your_package"
```

**Smallest fix path**

1. Fix one error class at a time (for example missing annotations or incompatible return types).
2. Rerun `python -m mypy ...` until clean.
3. Rerun full `python -m sdetkit gate fast`.

**Stay lightweight vs tighten later**

- Lightweight now: scope mypy to the package you are actively stabilizing.
- Tighten later: expand back to full `src` coverage.

---

## 3) `gate fast` failed on `pytest`

**What failed**

`gate fast: FAIL` and `failed_steps` includes `pytest`.

**Likely meaning**

Tests failed in the fast lane's default subset.

**Safest next commands**

```bash
# run default fast subset
python -m sdetkit gate fast --only pytest

# or run your own focused subset while triaging
python -m sdetkit gate fast --only pytest --pytest-args "-q tests/path_or_file.py"
```

**Smallest fix path**

1. Isolate one failing test module/class.
2. Fix deterministic failures first (assertions, setup, fixtures).
3. Rerun focused pytest, then rerun full `gate fast`.

**Stay lightweight vs tighten later**

- Lightweight now: keep PR enforcement on fast gate.
- Tighten later: use `--full-pytest` in stricter stages once flakiness is under control.

---

## 4) `security enforce` failed due to strict thresholds

**What failed**

`"ok": false` and `exceeded` shows counts over configured limits.

**Likely meaning**

Policy is stricter than your current baseline (often `info` findings first).

**Safest next commands**

```bash
# strict check
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0

# temporary adoption budget (example)
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 200
```

**Smallest fix path**

1. Keep `--max-error 0 --max-warn 0` (do not normalize serious findings).
2. Set `--max-info` close to current baseline.
3. Ratchet `--max-info` down on a schedule.

**Stay lightweight vs tighten later**

- Lightweight now: realistic info budget to avoid blocking all adoption.
- Tighten later: progressively lower budget until strict target is feasible.

---

## 5) `gate release` / `doctor --release` failed

**What failed**

`gate release: FAIL` and `failed_steps` includes `doctor_release`, `playbooks_validate`, or `gate_fast`.

**Likely meaning**

Release prerequisites are not met yet (often because fast gate is not green).

**Safest next commands**

```bash
# inspect release prerequisites directly
python -m sdetkit doctor --release --format json

# inspect release gate breakdown
python -m sdetkit gate release --format json --out build/gate-release.json
cat build/gate-release.json
```

**Smallest fix path**

1. Read `failed_steps` and clear them in order.
2. If `gate_fast` failed, fix that before retrying release gate.
3. Re-run release gate after prerequisites pass.

**Stay lightweight vs tighten later**

- Lightweight now: enforce only `gate fast` on PRs.
- Tighten later: apply `gate release` on release branches/tags.

---

## Guardrails (important)

- These playbooks are triage paths, not auto-fix guarantees.
- If the target repository has real code/test/security debt, the correct action is to fix the repository.
- Threshold tuning is for staged adoption, not permanent masking of failures.
