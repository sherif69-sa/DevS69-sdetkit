# Security and quality hardening lane

Date: 2026-10-13
Status: approved for planning after user review of this spec
Authority: review-first

## Goal

Make this repository safer to work in by using the existing quality and security commands, then fixing only in-repo fail-closed issues. Do not restart the product. Do not add a new control plane.

## Scope

One sequenced lane on this repository only:

1. Fail-closed local gates.
2. Actionable dependency upgrades or reviewed re-baselines.
3. Documented follow-ups that are true positives.

Work on a new branch from current `main`. Do not mix this work into `261013-feat-phase5-report-trust`.

In-repo fixes are allowed: code, tests, docs, pins, and reviewed audit baselines.

## Out of scope

- Auto-merge
- GitHub code-scanning or Dependabot alert dismissal
- Workflow permission expansion
- Patching other repositories
- New security dashboard, CI rewrite, or parallel report schema
- Package publish, merge to main without review, or 1.3.0 release
- Bulk dependency bumps without a failing audit or gate

## Authority

```text
review-first=true
patch_application_allowed=false outside this repository
security_dismissal_allowed=false
merge_authorized=false
publication_allowed=false
```

Passing doctor is `CONTINUE`, not SHIP. SHIP remains the two-artifact contract already implemented by the gate decision summary.

## Command sequence

Stop at the first fail-closed blocker. Fix that blocker with a failing test first, then continue.

1. `PYTHONPATH=src python3 -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json`
2. `bash security.sh`
3. `pip-audit --format json -o pip-audit-report.json -r requirements-test.txt -r requirements-docs.txt --ignore-vuln CVE-2026-4539 --ignore-vuln CVE-2025-69534` then `python3 .github/scripts/check_pip_audit_baseline.py` when a report exists. Install `pip-audit` from the existing CI pin if it is missing.
4. `PYTHONPATH=src python3 -m sdetkit doctor`
5. Only after those four: dependency upgrades or re-baselines, then documented follow-ups in `docs/security-code-scanning-followups.md`

Use `python3`. `python` is not assumed on PATH. Prefer `PYTHONPATH=src` for module commands.

## Error handling

- Missing, stale, malformed, or unavailable evidence fails closed. Do not treat unknown collection as an authoritative zero.
- One canonical next action per failure. Keep `authority=review-first`.
- If a gate or audit cannot run because a tool is missing, install only the existing project tool at the pinned version. Do not invent a scanner.
- If pip-audit reports a vulnerability already in `.github/pip-audit-baseline.json`, keep the baseline and record why. Do not silently widen ignores.
- If pip-audit reports a new vulnerability with a published fix, upgrade the pin in-repo and add or update tests/docs. If there is no actionable fixed version, add a narrow reviewed baseline note instead of a fake upgrade.
- Path-traversal and high-entropy findings in CLI path handling or docs/tests stay review-first. Fix true positives. Do not weaken scanners to hide them.
- Do not change `_is_failed` classification, SHIP contract, or doctor next-action card unless a failing test proves they are the blocker.

## Testing

TDD: no production change without a failing test first.

Minimum proof for each fix:

- One failing-path test for the insecure or failing behavior.
- One happy-path test that the intended command still works.

Verification commands after a fix:

```bash
python3 -m ruff check <changed-files>
PYTHONPATH=src python3 -m pytest -q <focused-tests>
```

Do not claim the lane is complete without a fresh run of the command that originally failed.

## Success criteria

- First fail-closed local gate either passes or has an in-repo fix with tests.
- No new ignored CVE unless a reviewed baseline note names the package, installed version, advisory id, and removal condition.
- No new control plane, no dismissed alerts, no auto-merge.
- Operator docs change only if a command or baseline the operator must run has changed.
- Remaining unfixed follow-ups stay listed with one next command each.

## Non-goals that look related

Phase 5 report-trust is already on PR 2336. This lane does not extend that PR.

CI wiring of new required checks is out of scope unless an existing local command cannot be run any other way.
