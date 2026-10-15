# Security and Quality Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make this repository safer to work in by running the existing fail-closed quality and security commands, then fixing only in-repo blockers.

**Architecture:** One sequenced review-first lane on this repository. Reuse `sdetkit gate fast`, `sdetkit security check`, `pip-audit` plus `.github/scripts/check_pip_audit_baseline.py`, and `sdetkit doctor`. Stop at the first fail-closed blocker, write a failing test, fix in-repo, re-run the same command. No new control plane, no auto-merge, no alert dismissal.

**Tech Stack:** Python 3.10+, `PYTHONPATH=src python3 -m sdetkit`, `pip-audit==2.10.1`, `ruff`, pytest, existing `safe_path` / `SecurityError` helpers.

## Global Constraints

- `review-first=true`
- `patch_application_allowed=false` outside this repository
- `security_dismissal_allowed=false`
- `merge_authorized=false`
- `publication_allowed=false`
- Use `python3`; do not assume `python` is on PATH except inside `security.sh` after venv activate
- Prefer `PYTHONPATH=src` for module commands
- TDD: no production change without a failing test first
- Passing doctor is `CONTINUE`, not SHIP
- Do not mix this work into `261013-feat-phase5-report-trust` / PR 2336
- Do not change `_is_failed`, the SHIP contract, or the doctor next-action card unless a failing test proves they are the blocker
- Do not invent a scanner, dashboard, or parallel report schema
- Work on branch `261013-feat-security-quality-hardening` from `origin/main`

## File map

- Run/read: `build/gate-fast.json`, `build/doctor.json`, `pip-audit-report.json`
- Run: `security.sh`, `.github/scripts/check_pip_audit_baseline.py`
- Pins/baselines: `requirements.txt`, `.github/workflows/dependency-audit.yml`, `.github/pip-audit-baseline.json`, `docs/security/pip-audit-baseline-notes.md`, `pyproject.toml`, `docs/ci/workflow-local-equivalents.md`
- Follow-ups: `docs/security-code-scanning-followups.md`
- Path guards: `src/sdetkit/security.py`, `src/sdetkit/apiget.py`, `src/sdetkit/cassette.py`
- Tests: `tests/test_security_hardening.py`, `tests/test_security_gate_cli.py`, new focused tests named in each task
- Operator docs: `docs/start-here-5-minutes.md` only if a command the operator must run changed

---

### Task 1: Clear `gate fast` or fix its first failure

**Files:**
- Read: `build/gate-fast.json` (generated)
- Test: `tests/test_security_hardening.py`
- Modify only files named by `next_action.affected_file` or the first failed step
- Do not modify: `src/sdetkit/check_intelligence.py`

**Interfaces:**
- Consumes: `python -m sdetkit gate fast` JSON with `ok`, `failed_steps`, `next_action`
- Produces: `build/gate-fast.json` where `ok` is true and `failed_steps` is `[]`, or an in-repo fix for `next_action.first_failure`
- `next_action` keys: `decision`, `classification`, `first_failure`, `affected_file`, `next_command`, `authority`
- Passing fast `decision` is `CONTINUE`; failing fast `decision` is `NO-SHIP`; `authority` is `review-first`

- [ ] **Step 1: Run gate fast**

```bash
mkdir -p build
PYTHONPATH=src python3 -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
echo EXIT:$?
```

Expected: process exits 0 or 1. File `build/gate-fast.json` exists.

- [ ] **Step 2: Read the artifact card**

```bash
PYTHONPATH=src python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("build/gate-fast.json").read_text(encoding="utf-8"))
print("ok", payload.get("ok"))
print("failed_steps", payload.get("failed_steps"))
print("next_action", json.dumps(payload.get("next_action"), indent=2, sort_keys=True))
PY
```

If `ok` is true and `failed_steps` is `[]`, skip to Step 6. Do not "improve" passing gates.

- [ ] **Step 3: Write the failing test for the first failure**

Only if Step 2 showed a failure. Put the test in `tests/test_security_hardening.py` using the artifact's `affected_file` / `first_failure`. Example shape when the card points at an unsafe path:

```python
from sdetkit.security import SecurityError, safe_path


def test_gate_fast_first_failure_still_blocks_traversal(tmp_path):
    try:
        safe_path(tmp_path, "../oops.txt")
    except SecurityError:
        return
    raise AssertionError("expected traversal to be rejected")
```

If `classification` is `ruff` or `pytest`, write the smallest test that reproduces `first_failure` instead of the example above. Do not copy a generic test that does not fail.

- [ ] **Step 4: Run the new test and confirm it fails**

```bash
PYTHONPATH=src python3 -m pytest -q tests/test_security_hardening.py -k first_failure
```

Expected: FAIL for the new test. If it passes, the test does not reproduce the blocker; rewrite it.

- [ ] **Step 5: Fix only the first failure and re-run**

Edit the file in `next_action.affected_file` (or the source of `failed_steps[0]`). Keep `authority=review-first`. Then:

```bash
python3 -m ruff check tests/test_security_hardening.py
PYTHONPATH=src python3 -m pytest -q tests/test_security_hardening.py
PYTHONPATH=src python3 -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
```

Expected: ruff clean, focused tests pass, `build/gate-fast.json` has `"ok": true` and `"failed_steps": []`.

- [ ] **Step 6: Commit**

```bash
git add tests/test_security_hardening.py
git add $(git diff --name-only)
git commit -m "fix(quality): clear the first gate-fast blocker"
```

If gate fast already passed and no files changed, do not create an empty commit.

---

### Task 2: Clear `security check` or fix its first warning/error at threshold

**Files:**
- Run: `security.sh` or `PYTHONPATH=src python3 -m sdetkit security check --format json --out build/security-check.json`
- Test: `tests/test_security_gate_cli.py`
- Modify: only the first finding's path from the JSON `findings` list
- Do not modify scanner rules in `src/sdetkit/gates/security_gate.py` to hide findings

**Interfaces:**
- Consumes: `sdetkit security check` JSON with `ok`, `findings`, `counts`
- Produces: `ok` true at default `--fail-on medium`, or an in-repo fix / reviewed inline allow for the first finding
- Inline allow form, only for proven false positives: `# sdetkit: allow-security <RULE_ID>`
- Do not add GitHub alert dismissals

- [ ] **Step 1: Run security check as JSON**

```bash
mkdir -p build
PYTHONPATH=src python3 -m sdetkit security check --format json --out build/security-check.json
echo EXIT:$?
```

If `sdetkit` is missing from the environment, use `bash security.sh` after the repo venv exists. Do not install a new scanner.

- [ ] **Step 2: Print the first finding at or above warn**

```bash
PYTHONPATH=src python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("build/security-check.json").read_text(encoding="utf-8"))
print("ok", payload.get("ok"))
print("counts", payload.get("counts"))
findings = payload.get("findings") or payload.get("new_findings") or []
rank = {"info": 1, "warn": 2, "error": 3}
above = [row for row in findings if rank.get(str(row.get("level") or row.get("severity")), 0) >= 2]
if not above:
    print("NO_BLOCKING_FINDING")
else:
    print(json.dumps(above[0], indent=2, sort_keys=True))
PY
```

If `NO_BLOCKING_FINDING` and `ok` is true, skip to Step 6.

- [ ] **Step 3: Write a failing test for that finding**

Add to `tests/test_security_gate_cli.py` when the first finding is a true positive in production code. Example for path traversal in a temp tree:

```python
def test_security_scan_flags_untrusted_path_join(tmp_path: Path, capsys) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text(
        "from pathlib import Path\nuser = input()\nPath(user)\n",
        encoding="utf-8",
    )
    rc = _run(["scan", "--root", str(tmp_path), "--format", "json", "--fail-on", "none"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    rule_ids = {row.get("rule_id") for row in payload.get("findings", [])}
    assert "SEC_POTENTIAL_PATH_TRAVERSAL" in rule_ids
```

If the first finding is already guarded by `safe_path` and the scanner is wrong, do not delete the rule. Write a happy-path test that `safe_path` rejects `../oops` and record the finding as remaining review-first in Task 6. Do not skip the rest of this task's re-run.

- [ ] **Step 4: Run the new test**

```bash
PYTHONPATH=src python3 -m pytest -q tests/test_security_gate_cli.py::test_security_scan_flags_untrusted_path_join
```

Expected: FAIL until the production fix exists, or PASS if this is the already-guarded false-positive proof. Only continue to Step 5 on a true-positive FAIL.

- [ ] **Step 5: Fix the first finding and re-run security check**

Use `safe_path(root, user_path)` for user path segments. Do not widen `--fail-on`. Then:

```bash
python3 -m ruff check tests/test_security_gate_cli.py
PYTHONPATH=src python3 -m pytest -q tests/test_security_gate_cli.py
PYTHONPATH=src python3 -m sdetkit security check --format json --out build/security-check.json
```

Expected: focused tests pass. If `ok` is still false, stop and keep the same first finding; do not batch-fix unrelated warnings in this task.

- [ ] **Step 6: Commit**

```bash
git add tests/test_security_gate_cli.py
git add $(git diff --name-only)
git commit -m "fix(security): clear the first security-check blocker"
```

Skip empty commits.

---

### Task 3: Align pip-audit pin, ignores, and baseline notes

**Files:**
- Modify: `docs/ci/workflow-local-equivalents.md`
- Modify: `.github/pip-audit-baseline.json` only if the checker requires CVE-2025-69534
- Modify: `docs/security/pip-audit-baseline-notes.md` if the installed version or ignore set changed
- Read: `.github/workflows/dependency-audit.yml`, `requirements.txt`, `pyproject.toml`
- Test: `tests/test_pip_audit_baseline_contract.py` (create)

**Interfaces:**
- Consumes: CI command `pip-audit --format json -o pip-audit-report.json -r requirements-test.txt -r requirements-docs.txt --ignore-vuln CVE-2026-4539 --ignore-vuln CVE-2025-69534`
- Consumes: `python3 .github/scripts/check_pip_audit_baseline.py`
- Produces: docs and baseline that match `pip-audit==2.10.1` and the two workflow ignores
- Do not add `CVE-2026-1703` to the workflow ignore list unless pip-audit currently reports it with no fix

- [ ] **Step 1: Write the failing contract test**

Create `tests/test_pip_audit_baseline_contract.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(".github/workflows/dependency-audit.yml")
NOTES = Path("docs/security/pip-audit-baseline-notes.md")
LOCAL_EQ = Path("docs/ci/workflow-local-equivalents.md")
REQUIREMENTS = Path("requirements.txt")


def test_pip_audit_pin_is_2_10_1() -> None:
    text = REQUIREMENTS.read_text(encoding="utf-8")
    assert "pip-audit==2.10.1" in text
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "pip-audit==2.10.1" in workflow
    local = LOCAL_EQ.read_text(encoding="utf-8")
    assert "pip-audit==2.10.1" in local
    assert "pip-audit==2.10.0" not in local


def test_workflow_ignore_set_is_documented() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    ignores = re.findall(r"--ignore-vuln\s+(\S+)", workflow)
    assert ignores == ["CVE-2026-4539", "CVE-2025-69534"]
    notes = NOTES.read_text(encoding="utf-8")
    assert "CVE-2026-4539" in notes
    assert "CVE-2025-69534" in notes
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
PYTHONPATH=src python3 -m pytest -q tests/test_pip_audit_baseline_contract.py
```

Expected: FAIL on `pip-audit==2.10.0` still present in `docs/ci/workflow-local-equivalents.md`.

- [ ] **Step 3: Write the minimal doc/baseline fix**

In `docs/ci/workflow-local-equivalents.md` replace the extracted install pin:

```bash
python -m pip install -c constraints-ci.txt pip-audit==2.10.1
python -m pip install -c constraints-ci.txt -e .
pip-audit --format json -o pip-audit-report.json -r requirements-test.txt -r requirements-docs.txt --ignore-vuln CVE-2026-4539 --ignore-vuln CVE-2025-69534
python .github/scripts/check_pip_audit_baseline.py
```

Keep `.github/pip-audit-baseline.json` as:

```json
[
  {
    "id": "CVE-2026-4539",
    "package": "pygments",
    "aliases": ["GHSA-5239-wwwm-4pmq"],
    "note": "Tracked in baseline while upstream advisory/fix guidance stabilizes."
  }
]
```

Do not add CVE-2025-69534 to that JSON while the workflow already passes `--ignore-vuln CVE-2025-69534`. The notes file already names package `markdown`, version `3.10.2`, id `PYSEC-2026-89`, alias `CVE-2025-69534`, and the removal condition. Leave the notes file unless the test still fails.

- [ ] **Step 4: Re-run the contract test**

```bash
PYTHONPATH=src python3 -m pytest -q tests/test_pip_audit_baseline_contract.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_pip_audit_baseline_contract.py docs/ci/workflow-local-equivalents.md docs/security/pip-audit-baseline-notes.md .github/pip-audit-baseline.json
git commit -m "docs(security): align pip-audit pin and ignore contract"
```

---

### Task 4: Run pip-audit and upgrade or re-baseline only actionable CVEs

**Files:**
- Generate: `pip-audit-report.json`
- Maybe modify: `requirements-test.txt`, `requirements-docs.txt`, `pyproject.toml`, `.github/pip-audit-baseline.json`, `docs/security/pip-audit-baseline-notes.md`
- Test: `tests/test_pip_audit_baseline_contract.py`
- Do not bulk-bump unrelated packages

**Interfaces:**
- Consumes: `pip-audit==2.10.1` from `requirements.txt`
- Produces: checker exit 0, or a new baseline entry with package, installed version, advisory id, and removal condition
- New ignore is forbidden unless that reviewed note exists

- [ ] **Step 1: Install the pinned auditor if missing**

```bash
python3 -m pip install --break-system-packages -c constraints-ci.txt pip-audit==2.10.1
```

If `constraints-ci.txt` is absent from this checkout, use `python3 -m pip install --break-system-packages pip-audit==2.10.1`.

- [ ] **Step 2: Run the same audit CI runs**

```bash
pip-audit --format json -o pip-audit-report.json \
  -r requirements-test.txt \
  -r requirements-docs.txt \
  --ignore-vuln CVE-2026-4539 \
  --ignore-vuln CVE-2025-69534
python3 .github/scripts/check_pip_audit_baseline.py
echo EXIT:$?
```

If both commands exit 0 with `No vulnerabilities beyond baseline.`, skip to Step 6.

- [ ] **Step 3: Write a failing test for a new vulnerability**

If the checker prints `New vulnerabilities found: - <CVE-ID> (package)`, add to `tests/test_pip_audit_baseline_contract.py`:

```python
def test_new_audit_ids_are_not_silently_ignored() -> None:
    workflow = Path(".github/workflows/dependency-audit.yml").read_text(encoding="utf-8")
    assert "--ignore-vuln <CVE-ID>" not in workflow
```

Replace `<CVE-ID>` with the real id. Expected FAIL only if someone already hid it; if this assertion already passes, go to Step 4 and write the upgrade or baseline instead.

- [ ] **Step 4: Upgrade when a published fix exists**

If `pip-audit-report.json` lists `fix_versions` for that package, pin the lowest published fix in the same file that currently pins the package (`requirements-test.txt` or `requirements-docs.txt` or `pyproject.toml`). Do not upgrade neighbors.

If `fix_versions` is empty, append one object to `.github/pip-audit-baseline.json`:

```json
{
  "id": "<CVE-ID>",
  "package": "package-name",
  "aliases": [],
  "note": "No published fix_versions in pip-audit 2.10.1. Remove when a fixed version is published."
}
```

And add a section to `docs/security/pip-audit-baseline-notes.md` with package, installed version, advisory id, and removal condition. Do not add `--ignore-vuln` for it unless the CI command cannot see it any other way.

- [ ] **Step 5: Re-run audit and tests**

```bash
pip-audit --format json -o pip-audit-report.json \
  -r requirements-test.txt \
  -r requirements-docs.txt \
  --ignore-vuln CVE-2026-4539 \
  --ignore-vuln CVE-2025-69534
python3 .github/scripts/check_pip_audit_baseline.py
PYTHONPATH=src python3 -m pytest -q tests/test_pip_audit_baseline_contract.py
```

Expected: checker prints `No vulnerabilities beyond baseline.` and tests PASS.

- [ ] **Step 6: Commit**

```bash
git add requirements-test.txt requirements-docs.txt pyproject.toml .github/pip-audit-baseline.json docs/security/pip-audit-baseline-notes.md tests/test_pip_audit_baseline_contract.py
git commit -m "fix(security): close actionable pip-audit findings"
```

Skip empty commits. Do not commit `pip-audit-report.json`.

---

### Task 5: Clear doctor or record its review-first next action

**Files:**
- Generate: `build/doctor.json`
- Test: `tests/test_doctor_next_action.py` if a doctor failure needs an in-repo fix
- Modify only the file in `next_action.affected_file`
- Do not change `src/sdetkit/doctor.py` `_next_action_card` unless the failing test proves the card itself is wrong

**Interfaces:**
- Consumes: `python -m sdetkit doctor --format json --out build/doctor.json`
- Produces: passing doctor `next_action.decision == "CONTINUE"` and empty `next_command`, or a NO-SHIP card with `authority=review-first`
- Passing doctor is not SHIP

- [ ] **Step 1: Run doctor**

```bash
mkdir -p build
PYTHONPATH=src python3 -m sdetkit doctor --format json --out build/doctor.json
echo EXIT:$?
```

- [ ] **Step 2: Print the card**

```bash
PYTHONPATH=src python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("build/doctor.json").read_text(encoding="utf-8"))
print("ok", payload.get("ok"))
print("failed_checks", payload.get("failed_checks"))
print("next_action", json.dumps(payload.get("next_action"), indent=2, sort_keys=True))
PY
```

If `ok` is true and `failed_checks` is `[]`, the card must be `decision=CONTINUE`, `next_command=""`, `authority=review-first`. Skip to Step 6.

- [ ] **Step 3: Write a failing test for the first doctor check**

Only if doctor failed. Add `tests/test_doctor_next_action.py` only when the existing doctor tests do not cover this check. Prefer extending the existing doctor test module that already names `failed_checks[0]`. The new test must fail on current code.

- [ ] **Step 4: Run that test**

```bash
PYTHONPATH=src python3 -m pytest -q tests/test_doctor_next_action.py
```

Expected: FAIL. If you did not create that file because an existing test already fails, run that existing file instead.

- [ ] **Step 5: Fix the first doctor check and re-run doctor**

```bash
python3 -m ruff check $(git diff --name-only -- '*.py')
PYTHONPATH=src python3 -m pytest -q tests/test_doctor_next_action.py
PYTHONPATH=src python3 -m sdetkit doctor --format json --out build/doctor.json
```

Expected: focused tests pass. Re-read `next_action`. If still NO-SHIP, stop at that first check; do not start a second doctor fix in this task.

- [ ] **Step 6: Commit**

```bash
git add $(git diff --name-only)
git commit -m "fix(doctor): clear the first doctor blocker"
```

Skip empty commits.

---

### Task 6: Close documented path-traversal follow-ups without weakening the scanner

**Files:**
- Test: `tests/test_security_hardening.py`
- Read: `src/sdetkit/apiget.py`, `src/sdetkit/cassette.py`, `src/sdetkit/security.py`
- Modify: `docs/security-code-scanning-followups.md`
- Do not add `# sdetkit: allow-security SEC_POTENTIAL_PATH_TRAVERSAL` unless a test proves `safe_path` already rejects the input and the remaining finding is AST noise

**Interfaces:**
- Consumes: `safe_path(root: Path, user_path: str, *, allow_absolute: bool = False) -> Path`
- Consumes: `SecurityError`
- Produces: tests that `@../secret` and cassette `../secret.json` fail closed, plus an updated follow-up doc with one next command for anything still open

- [ ] **Step 1: Write failing tests for the two follow-up files**

Append to `tests/test_security_hardening.py`:

```python
from pathlib import Path

from sdetkit import apiget
from sdetkit.cassette import Cassette
from sdetkit.security import SecurityError


def test_apiget_at_file_rejects_traversal(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ok.txt").write_text("hello", encoding="utf-8")
    try:
        apiget.main(["https://example.test/", "--data", "@../oops.txt"])
    except SystemExit as exc:
        assert int(exc.code) == 2
    else:
        raise AssertionError("expected SystemExit(2) for traversal at-file")


def test_cassette_save_rejects_traversal(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    cassette = Cassette([])
    try:
        cassette.save("../oops.json")
    except SecurityError:
        return
    raise AssertionError("expected cassette traversal to be rejected")
```

- [ ] **Step 2: Run the new tests**

```bash
PYTHONPATH=src python3 -m pytest -q tests/test_security_hardening.py::test_apiget_at_file_rejects_traversal tests/test_security_hardening.py::test_cassette_save_rejects_traversal
```

Expected: FAIL if the guards are missing. If both PASS, the production code already fails closed; go to Step 4 without changing `apiget.py` or `cassette.py`.

- [ ] **Step 3: Implement only if tests failed**

Keep using `safe_path(Path.cwd(), path, allow_absolute=bool(...))` in `src/sdetkit/apiget.py` `_read_at_file_text` / `_read_at_file_bytes` and in `Cassette.save` / `Cassette.load` / `open_transport`. Do not set `allow_absolute=True` for at-file reads unless the CLI flag `--allow-absolute-path` is set. Re-run Step 2 until PASS.

- [ ] **Step 4: Update the follow-up doc**

Replace the "Locally triaged findings" list in `docs/security-code-scanning-followups.md` with current status. If the two tests passed, mark those two items resolved and keep high-entropy docs/tests as review-first:

```markdown
## Locally triaged findings to track

1. `SEC_POTENTIAL_PATH_TRAVERSAL` in `src/sdetkit/apiget.py`: at-file reads go through `safe_path`. Proof: `tests/test_security_hardening.py::test_apiget_at_file_rejects_traversal`.
2. `SEC_POTENTIAL_PATH_TRAVERSAL` in `src/sdetkit/cassette.py`: cassette paths go through `safe_path`. Proof: `tests/test_security_hardening.py::test_cassette_save_rejects_traversal`.
3. `SEC_HIGH_ENTROPY_STRING` in docs/tests remains review-first. Next command: `PYTHONPATH=src python3 -m sdetkit security check --format json --out build/security-check.json`.
```

Do not dismiss GitHub alerts.

- [ ] **Step 5: Re-run focused tests and security check**

```bash
python3 -m ruff check tests/test_security_hardening.py src/sdetkit/apiget.py src/sdetkit/cassette.py
PYTHONPATH=src python3 -m pytest -q tests/test_security_hardening.py
PYTHONPATH=src python3 -m sdetkit security check --format json --out build/security-check.json
```

Expected: ruff clean, tests PASS. Remaining findings stay listed, not dismissed.

- [ ] **Step 6: Commit**

```bash
git add tests/test_security_hardening.py docs/security-code-scanning-followups.md src/sdetkit/apiget.py src/sdetkit/cassette.py
git commit -m "test(security): prove at-file and cassette paths fail closed"
```

---

### Task 7: Final proof of the four commands

**Files:**
- Read only unless a command the operator must run changed: `docs/start-here-5-minutes.md`
- Do not add a new dashboard

**Interfaces:**
- Consumes: Tasks 1-6 artifacts and commits
- Produces: fresh passing output from the four lane commands, or one remaining next_action per still-open item

- [ ] **Step 1: Re-run the four commands fresh**

```bash
PYTHONPATH=src python3 -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
PYTHONPATH=src python3 -m sdetkit security check --format json --out build/security-check.json
pip-audit --format json -o pip-audit-report.json \
  -r requirements-test.txt \
  -r requirements-docs.txt \
  --ignore-vuln CVE-2026-4539 \
  --ignore-vuln CVE-2025-69534
python3 .github/scripts/check_pip_audit_baseline.py
PYTHONPATH=src python3 -m sdetkit doctor --format json --out build/doctor.json
```

Expected: each command either exits 0 or has a printed next action already recorded in a previous task commit. Do not claim completion if any command was skipped.

- [ ] **Step 2: Update operator docs only if a command changed**

If Task 3 or 4 changed the pip-audit command the operator runs, add the same command block under security notes in `docs/start-here-5-minutes.md`. If the command did not change, do not touch that file.

- [ ] **Step 3: Focused lint and tests for files this branch changed**

```bash
python3 -m ruff check tests/test_pip_audit_baseline_contract.py tests/test_security_hardening.py docs/ci/workflow-local-equivalents.md
PYTHONPATH=src python3 -m pytest -q tests/test_pip_audit_baseline_contract.py tests/test_security_hardening.py tests/test_security_gate_cli.py
```

Expected: PASS.

- [ ] **Step 4: Commit remaining doc-only edits**

```bash
git add docs/start-here-5-minutes.md
git commit -m "docs(security): record the operator audit command"
```

Skip if `docs/start-here-5-minutes.md` is unchanged.
