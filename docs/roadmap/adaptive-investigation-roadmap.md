# Adaptive Investigation Roadmap

## Executive summary

SDETKit is evolving from a collection of strong diagnostic and maintenance tools into a connected deterministic repo investigator and, later, a guarded auto-fix system.

The product spine is:

```text
detect → diagnose → recommend → plan → prove → classify → trend → candidate → probation → policy proposal → dry run → guarded PR auto-fix → remember outcome
```

The investigation spine is:

```text
scan → narrow → reproduce → classify → recommend → verify → remember
```

The immediate goal is not to enable broad automation. The immediate goal is to make SDETKit better at understanding failures, explaining why they matter, recommending safe next actions, collecting proof, and remembering outcomes. Auto-fix should launch later, only for narrow mechanical classes with repeated proof and explicit policy gates.

The most important architecture rule is: **do not build a second investigator brain.** The new `investigate` surface should be a thin human-friendly front door over existing shared engines. The shared classification brain remains `adaptive_diagnosis`; maintenance, review, mission-control, boost/index, and forensics should call into it or contribute evidence to it.

---

## Current foundation

SDETKit already has the right base pieces. The roadmap should connect and deepen these systems rather than replace them.

### Existing intelligence and evidence layers

- `adaptive_diagnosis` already acts as the shared failure classification layer.
- `maintenance_autopilot` already acts as the CI/autopilot caller and writes diagnosis, remediation, safe-fix, and learning artifacts.
- `review` orchestrates doctor, inspect, readiness, comparison, probe planning, contradiction clustering, confidence scoring, and history-aware evidence.
- `mission-control` bundles release evidence, gate/doctor/readiness steps, stdout/stderr artifacts, findings, next actions, Doctor Cortex, and run history.
- `boost` and `index` scan repo shape, high-signal files, risk markers, hotspots, symbols, adaptive memory, and risk hygiene.
- `forensics` compares run records and builds deterministic repro/evidence bundles.
- PR quality comments and maintenance issue comments already publish operator-facing summaries.

### Recent maintenance roadmap already merged

Recent PRs established a maintenance intelligence chain:

```text
maintenance run
  ↓
maintenance priority rollup
  ↓
maintenance policy decisions
  ↓
policy decision history
  ↓
policy memory context
  ↓
adaptive maintenance recommendations
  ↓
recommendation eligibility diagnostics
  ↓
maintenance action plan
```

The current merged behavior is intentionally conservative:

```text
diagnostic_only: true
automation_allowed: false
auto_fix_enabled: false
```

That is correct. The system can now recommend and plan, but it should not auto-fix until the proof, category, trend, candidate, probation, and policy proposal layers are mature.

### Real workflow guide from PR #1155

A real product gap around async/client/helper envelope pagination parity showed what SDETKit should learn to do automatically:

```text
scan → narrow → reproduce → classify → recommend → verify → remember
```

The manual process surfaced recurring failure classes that should become first-class diagnosis families:

- formatting drift from pre-commit / Ruff format
- Ruff fixable lint
- missing test dependencies
- Python runtime compatibility problems
- local WSL or `/mnt/c` environment friction
- broken test doubles
- missing public API parity
- git branch divergence
- remote branch drift after bot or remote updates
- product logic failures
- unknown review-required failures

---

## Architecture roles

Keep responsibilities separate and composable.

| Component | Role | Should do | Should not do |
|---|---|---|---|
| `adaptive_diagnosis` | Shared failure-classification brain | Classify failure logs and structured evidence into deterministic diagnosis families | Own CI, comments, repo scanning, or remediation execution |
| `maintenance_autopilot` | CI/autopilot caller | Invoke checks, collect artifacts, call diagnosis/policy layers, optionally commit only approved safe fixes | Become the diagnosis brain |
| `review` | Evidence orchestration and decision layer | Combine doctor/inspect/readiness/probe evidence into review decisions | Duplicate boost/index/forensics classification logic |
| `mission-control` | Release evidence bundle | Package release confidence evidence and run history | Decide low-level fix policies |
| `boost` / `index` | Repo and surface scan | Produce repo shape, symbols, hotspots, risk markers, high-signal files | Emit final failure decisions alone |
| `forensics` | Compare/bundle/repro evidence | Compare runs, preserve logs, generate repro bundles | Choose remediation policy |
| `investigate` | Human-friendly front door | Wrap diagnosis, repo scan, surface scan, and evidence bundles into simple commands | Duplicate adaptive diagnosis, boost, index, review, or maintenance logic |
| safe-fix policy | Guardrail layer | Decide which diagnosis classes may become auto-fix candidates | Auto-fix product/API gaps or ambiguous failures |
| outcome memory | Learning loop | Record repeated signals, proof, fixes, failures, PR outcomes, time-to-green | Override policy gates without proof |

---

## Product principles

1. **Classify before recommending.** Every recommendation should be grounded in a diagnosis family or explicit unknown/review-required state.
2. **Recommend before fixing.** Recommendations should explain what to do, why, and what proof is needed.
3. **Proof before candidates.** An item should not become an auto-fix candidate until the proof checklist is satisfiable and history supports it.
4. **Candidates before policy.** A candidate registry should exist before any auto-fix policy proposal.
5. **Policy before execution.** Auto-fix should only run after an explicit policy PR or equivalent reviewed configuration change.
6. **Dry run before write.** Planned changes should be visible before any modifying run.
7. **PR-only execution.** Guarded auto-fix should open a PR, never push directly to `main`.
8. **Outcome memory closes the loop.** Every attempt, success, failure, human edit, revert, and proof command should feed future diagnosis and recommendations.

---

## Phase-by-phase roadmap

## Phase 1 — Upgrade the shared diagnosis brain

### Goal

Teach `adaptive_diagnosis` the local investigation failure classes that appeared during real repo work, so later roadmap layers consume one shared classification model.

### PR 1: Expand adaptive diagnosis for local investigation failures

Suggested branch:

```text
feature/adaptive-diagnosis-local-investigation-failures
```

Suggested PR title:

```text
Expand adaptive diagnosis for local investigation failures
```

Diagnosis families to add:

```text
PRE_COMMIT_FORMAT_DRIFT
RUFF_FIXABLE_LINT
MISSING_TEST_DEPENDENCY
PYTHON_RUNTIME_COMPATIBILITY
LOCAL_ENVIRONMENT_FRICTION
BROKEN_TEST_DOUBLE
MISSING_PUBLIC_API_PARITY
GIT_BRANCH_DIVERGED
REMOTE_BRANCH_DRIFT
PRODUCT_LOGIC_FAILURE
UNKNOWN_REVIEW_REQUIRED
```

Representative signal mapping:

| Diagnosis | Example signals | Default route | Auto-fix candidate? |
|---|---|---|---|
| `PRE_COMMIT_FORMAT_DRIFT` | `ruff-format`, `end-of-file-fixer`, `files were modified by this hook` | safe mechanical review or auto-fix candidate | yes, later |
| `RUFF_FIXABLE_LINT` | Ruff fixable lint output, `--fix` suggestion | narrow mechanical candidate | yes, later |
| `MISSING_TEST_DEPENDENCY` | `ModuleNotFoundError`, missing `hypothesis`, missing `yaml` | environment/dependency guidance | no |
| `PYTHON_RUNTIME_COMPATIBILITY` | `ImportError: cannot import name 'UTC' from datetime` | compatibility PR | no |
| `LOCAL_ENVIRONMENT_FRICTION` | venv/pip hangs, slow paths under `/mnt/c`, WSL friction | environment guidance | no |
| `BROKEN_TEST_DOUBLE` | `TypeError: Resp() takes no arguments`, broken mock/init | review-first test fix | no by default |
| `MISSING_PUBLIC_API_PARITY` | async method missing while sync method exists, helper/API mismatch | product implementation | no |
| `GIT_BRANCH_DIVERGED` | push rejected, fetch first, non-fast-forward | command guidance | no |
| `REMOTE_BRANCH_DRIFT` | local branch behind PR branch after bot/remote update | sync guidance | no |
| `PRODUCT_LOGIC_FAILURE` | deterministic assertion failure in product behavior | review-first product fix | no |
| `UNKNOWN_REVIEW_REQUIRED` | no confident class | review-first | no |

Output contract:

```json
{
  "schema_version": "sdetkit.adaptive.diagnosis.v2",
  "classification": "MISSING_PUBLIC_API_PARITY",
  "confidence": "high",
  "product_logic_likely": true,
  "test_bug_likely": false,
  "environment_likely": false,
  "git_workflow_likely": false,
  "formatting_likely": false,
  "safe_to_auto_fix": false,
  "requires_human_review": true,
  "summary": "Missing async public API parity detected.",
  "why_it_matters": "The async client lacks a public method available on the sync client.",
  "next_action": "Add async parity and focused helper-level coverage.",
  "proof_commands": [
    "PYTHONPATH=src python -m pytest -q tests/test_netclient_envelope_parity.py"
  ],
  "memory_lookup_key": "diagnosis:MISSING_PUBLIC_API_PARITY:netclient"
}
```

Tests:

```bash
PYTHONPATH=src python -m pytest -q tests/test_adaptive_diagnosis.py
python -m pre_commit run -a
./scripts/pr_preflight.sh
```

Acceptance criteria:

- Each new class has a deterministic test fixture.
- Unknown cases fall back to `UNKNOWN_REVIEW_REQUIRED`.
- Only narrow mechanical classes can return `safe_to_auto_fix: true`.
- Product/API/test/runtime/dependency/git-drift classes remain review-first.

---

## Phase 2 — Align maintenance action categories with diagnosis classes

### Goal

Let maintenance action plans consume richer diagnosis categories instead of inventing separate category logic.

### PR 2: Add maintenance action categories using diagnosis classes

Suggested branch:

```text
feature/maintenance-action-diagnosis-categories
```

Suggested PR title:

```text
Classify maintenance actions with adaptive diagnosis classes
```

Outputs:

```text
artifacts/maintenance-action-categories.json
artifacts/maintenance-action-categories.md
```

JSON contract:

```json
{
  "schema_version": "sdetkit.maintenance.action_categories.v1",
  "diagnostic_only": true,
  "automation_allowed": false,
  "category_count": 10,
  "counts_by_category": {
    "formatting": 1,
    "tests": 1,
    "security": 1,
    "workflow_hygiene": 1
  },
  "items": [
    {
      "rank": 1,
      "signal": "Run ruff check",
      "memory_lookup_key": "maintenance-action:lint_check:ruff-check",
      "diagnosis_class": "RUFF_FIXABLE_LINT",
      "category": "lint",
      "risk_level": "low",
      "safe_fix_route": "candidate_later",
      "review_required": true,
      "reason": "Ruff lint may be mechanically fixable, but policy proof is still required."
    }
  ]
}
```

Markdown contract:

```markdown
# Maintenance action categories

- diagnostic only: **True**
- automation allowed: **False**
- categories: **N**

## Category mix

| Category | Count | Safe-fix route |
|---|---:|---|

## Classified actions

| Rank | Category | Diagnosis | Risk | Signal | Route |
|---:|---|---|---|---|---|
```

Tests:

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_maintenance_action_categories.py \
  tests/test_maintenance_on_demand_action_categories_workflow.py
./scripts/pr_preflight.sh
```

Acceptance criteria:

- Uses `adaptive_diagnosis` classes where possible.
- Does not enable auto-fix.
- Uploads JSON/Markdown artifacts.
- Adds an issue-comment section after action plan and before lower-level recommendation detail.

---

## Phase 3 — Add proof checklist

### Goal

Turn action-plan items into explicit evidence requirements. This is the bridge between “recommend” and “can progress.”

### PR 3: Publish maintenance proof checklist

Suggested branch:

```text
feature/maintenance-proof-checklist
```

Suggested PR title:

```text
Publish maintenance proof checklist
```

Outputs:

```text
artifacts/maintenance-proof-checklist.json
artifacts/maintenance-proof-checklist.md
```

JSON contract:

```json
{
  "schema_version": "sdetkit.maintenance.proof_checklist.v1",
  "diagnostic_only": true,
  "automation_allowed": false,
  "proof_item_count": 10,
  "complete_count": 0,
  "missing_count": 10,
  "items": [
    {
      "rank": 8,
      "signal": "Run pytest -q",
      "memory_lookup_key": "maintenance-action:tests_check:run-tests",
      "diagnosis_class": "PRODUCT_LOGIC_FAILURE",
      "required_proof": "Attach passing pytest output.",
      "proof_status": "missing",
      "proof_commands": [
        "python -m pytest -q"
      ],
      "required_artifacts": [
        "pytest output"
      ],
      "can_progress_to_candidate": false,
      "blocking_reason": "Review proof has not been attached."
    }
  ]
}
```

Markdown contract:

```markdown
# Maintenance proof checklist

- diagnostic only: **True**
- proof items: **N**
- missing proof: **N**

## Proof checklist

| Rank | Signal | Diagnosis | Proof status | Required proof | Can progress |
|---:|---|---|---|---|---|
```

Tests:

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_maintenance_proof_checklist.py \
  tests/test_maintenance_on_demand_proof_checklist_workflow.py
./scripts/pr_preflight.sh
```

Acceptance criteria:

- Every action-plan item gets a proof row.
- Missing proof blocks candidate progression.
- Mechanical classes still require repeated/history evidence before auto-fix policy changes.

---

## Phase 4 — Add signal trends

### Goal

Use memory/history to distinguish one-off signals from repeated signals and prior successful fixes.

### PR 4: Publish maintenance signal trend summary

Suggested branch:

```text
feature/maintenance-signal-trends
```

Suggested PR title:

```text
Publish maintenance signal trend summary
```

Outputs:

```text
artifacts/maintenance-signal-trends.json
artifacts/maintenance-signal-trends.md
```

JSON contract:

```json
{
  "schema_version": "sdetkit.maintenance.signal_trends.v1",
  "diagnostic_only": true,
  "automation_allowed": false,
  "signals": [
    {
      "memory_lookup_key": "maintenance-action:lint_check:ruff-check",
      "signal": "Run ruff check",
      "diagnosis_class": "RUFF_FIXABLE_LINT",
      "seen_count": 4,
      "recent_count": 2,
      "safe_fix_attempts": 1,
      "safe_fix_successes": 1,
      "trend": "recurring",
      "trend_confidence": "medium",
      "recommendation_impact": "candidate_later"
    }
  ]
}
```

Tests:

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_maintenance_signal_trends.py \
  tests/test_maintenance_on_demand_signal_trends_workflow.py
./scripts/pr_preflight.sh
```

Acceptance criteria:

- Uses policy decision history and memory context.
- Repeated signals are visible.
- Trends affect recommendations only diagnostically at this stage.

---

## Phase 5 — Add human-friendly investigation front door

### Goal

Expose shared adaptive diagnosis directly to humans through a thin command surface.

### PR 5: Add failure investigation command

Suggested branch:

```text
feature/investigate-failure-command
```

Suggested PR title:

```text
Add failure investigation command
```

Commands:

```bash
python -m sdetkit investigate failure --log quality.log --format json
python -m sdetkit investigate failure --log quality.log --format markdown
```

Output fields:

```text
classification
confidence
likely type
recommended next command
proof commands
safe-fix eligibility
memory lookup key
```

Example Markdown:

```markdown
# Failure investigation

- classification: **MISSING_PUBLIC_API_PARITY**
- confidence: **high**
- likely type: **product/API gap**
- safe to auto-fix: **False**
- requires human review: **True**

## Why

The log shows an AttributeError for a missing async method while the sync method exists.

## Next action

Add async parity and helper-level coverage, then run the focused test slice.

## Proof commands

```bash
PYTHONPATH=src python -m pytest -q tests/test_netclient_envelope_parity.py
```
```

Tests:

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_investigate_failure.py \
  tests/test_adaptive_diagnosis.py
python -m pre_commit run -a
```

Acceptance criteria:

- Calls `adaptive_diagnosis`; does not duplicate classification logic.
- Supports JSON and Markdown.
- Exits nonzero only for malformed inputs, not for diagnosed failures.

---

## Phase 6 — Add repository investigation summary

### Goal

Use `boost` and `index` evidence to choose where to investigate next.

### PR 6: Add repository investigation summary

Suggested branch:

```text
feature/investigate-repo-summary
```

Suggested PR title:

```text
Add repository investigation summary
```

Command:

```bash
python -m sdetkit investigate repo --root . --format json
```

JSON contract:

```json
{
  "schema_version": "sdetkit.investigate.repo.v1",
  "repo_shape": {
    "source_files": 328,
    "test_files": 591,
    "workflow_files": 18
  },
  "top_surfaces": [
    {
      "name": "netclient",
      "production_files": [
        "src/sdetkit/netclient.py"
      ],
      "test_files": [
        "tests/test_netclient.py"
      ],
      "reason": "bounded HTTP client surface with sync/async/API/CLI parity risk",
      "recommended_next_probe": "investigate surface --surface netclient"
    }
  ]
}
```

Tests:

```bash
PYTHONPATH=src python -m pytest -q tests/test_investigate_repo.py
./scripts/pr_preflight.sh
```

Acceptance criteria:

- Wraps or consumes boost/index outputs.
- Produces concise operator-facing surface choices.
- Does not replace boost or index.

---

## Phase 7 — Add focused surface investigation

### Goal

Automate the manual narrowing work performed for `netclient` and similar surfaces.

### PR 7: Add focused surface investigation

Suggested branch:

```text
feature/investigate-surface
```

Suggested PR title:

```text
Add focused surface investigation
```

Command:

```bash
python -m sdetkit investigate surface --root . --surface netclient --format json
```

JSON contract:

```json
{
  "schema_version": "sdetkit.investigate.surface.v1",
  "surface": "netclient",
  "production_files": [
    "src/sdetkit/netclient.py",
    "src/sdetkit/apiclient.py",
    "src/sdetkit/apiget.py"
  ],
  "test_files": [
    "tests/test_netclient.py"
  ],
  "public_symbols": [
    "SdetHttpClient.get_json_list_paginated_envelope",
    "SdetAsyncHttpClient.get_json_list_paginated"
  ],
  "parity_risks": [
    {
      "kind": "sync_async_method_gap",
      "sync_symbol": "get_json_list_paginated_envelope",
      "async_symbol": "get_json_list_paginated_envelope",
      "status": "missing"
    }
  ],
  "recommended_probe": "write focused parity repro"
}
```

Tests:

```bash
PYTHONPATH=src python -m pytest -q tests/test_investigate_surface.py
./scripts/pr_preflight.sh
```

---

## Phase 8 — Add deterministic parity detectors

### Goal

Catch sync/async/helper/CLI/public-mode parity gaps before humans manually find them.

### PR 8: Detect public API parity gaps

Suggested branch:

```text
feature/public-api-parity-detectors
```

Suggested PR title:

```text
Detect public API parity gaps
```

Detector families:

```text
SYNC_ASYNC_METHOD_GAP
SYNC_ASYNC_HELPER_GAP
CLI_BACKEND_PARITY_GAP
PUBLIC_MODE_UNTESTED
```

JSON contract:

```json
{
  "schema_version": "sdetkit.investigate.parity.v1",
  "surface": "netclient",
  "findings": [
    {
      "kind": "SYNC_ASYNC_METHOD_GAP",
      "severity": "warning",
      "sync_symbol": "SdetHttpClient.get_json_list_paginated_envelope",
      "async_symbol": "SdetAsyncHttpClient.get_json_list_paginated_envelope",
      "status": "missing",
      "recommended_test": "focused sync/async parity test"
    }
  ]
}
```

Tests:

```bash
PYTHONPATH=src python -m pytest -q tests/test_public_api_parity_detectors.py
./scripts/pr_preflight.sh
```

Acceptance criteria:

- Deterministic AST-based checks.
- No import-time side effects.
- Detects known PR #1155-style gap from a fixture.

---

## Phase 9 — Generate investigation evidence bundles

### Goal

Write durable evidence artifacts for candidate freeze, audit result, proof commands, and investigation JSON.

### PR 9: Write investigation candidate evidence

Suggested branch:

```text
feature/investigation-evidence-writer
```

Suggested PR title:

```text
Write investigation candidate evidence
```

Command:

```bash
python -m sdetkit investigate evidence \
  --classification MISSING_PUBLIC_API_PARITY \
  --surface netclient \
  --out-dir build/investigate/netclient
```

Generated files:

```text
build/investigate/netclient/CANDIDATE_FREEZE.md
build/investigate/netclient/AUDIT_RESULT.md
build/investigate/netclient/proof-commands.md
build/investigate/netclient/investigation.json
```

Tests:

```bash
PYTHONPATH=src python -m pytest -q tests/test_investigate_evidence.py
./scripts/pr_preflight.sh
```

---

## Phase 10 — Route investigation diagnoses through safe-fix policy

### Goal

Connect diagnosis classes to safe-fix eligibility without enabling broad automation.

### PR 10: Route investigation diagnoses through safe-fix policy

Suggested branch:

```text
feature/investigation-safe-fix-policy-routing
```

Suggested PR title:

```text
Route investigation diagnoses through safe-fix policy
```

Policy matrix:

| Diagnosis | Auto-fix? | Route |
|---|---:|---|
| `PRE_COMMIT_FORMAT_DRIFT` | yes, later | safe mechanical |
| `RUFF_FIXABLE_LINT` | yes, narrow, later | safe mechanical |
| `GIT_BRANCH_DIVERGED` | no | command guidance |
| `REMOTE_BRANCH_DRIFT` | no | sync guidance |
| `MISSING_TEST_DEPENDENCY` | no | environment guidance |
| `PYTHON_RUNTIME_COMPATIBILITY` | no | compatibility PR |
| `LOCAL_ENVIRONMENT_FRICTION` | no | local environment guidance |
| `BROKEN_TEST_DOUBLE` | no by default | review-first test fix |
| `MISSING_PUBLIC_API_PARITY` | no | product implementation |
| `PRODUCT_LOGIC_FAILURE` | no | review-first product fix |
| `UNKNOWN_REVIEW_REQUIRED` | no | review-first |

Tests:

```bash
PYTHONPATH=src python -m pytest -q tests/test_investigation_safe_fix_policy.py
./scripts/pr_preflight.sh
```

Acceptance criteria:

- Broad diagnosis does not imply broad auto-fix.
- Only mechanical classes can be candidates.
- Candidate still requires history/proof/policy before execution.

---

## Phase 11 — Publish investigation summaries in PR comments

### Goal

When CI fails, PR comments should show classification, confidence, safe-fix status, next proof command, and memory context.

### PR 11: Publish investigation summaries for PR failures

Suggested branch:

```text
feature/pr-investigation-summaries
```

Suggested PR title:

```text
Publish investigation summaries for PR failures
```

Comment section example:

```markdown
### Failure investigation

- classification: **PRE_COMMIT_FORMAT_DRIFT**
- confidence: **high**
- safe-fix status: **candidate later**
- next command: `python -m pre_commit run -a`
- memory: seen 2 times, fixed manually 2 times
```

Tests:

```bash
PYTHONPATH=src python -m pytest -q tests/test_pr_investigation_summary_workflow.py
./scripts/pr_preflight.sh
```

---

## Phase 12 — Remember investigation outcomes

### Goal

Turn investigation outputs into durable memory that improves future recommendations, eligibility, action plans, safe-fix candidates, and risk scoring.

### PR 12: Record investigation outcome memory

Suggested branch:

```text
feature/investigation-outcome-memory
```

Suggested PR title:

```text
Record investigation outcome memory
```

Memory fields:

```json
{
  "schema_version": "sdetkit.investigation.outcome_memory.v1",
  "records": [
    {
      "classification": "PRE_COMMIT_FORMAT_DRIFT",
      "surface": "tests",
      "affected_files": ["tests/test_example.py"],
      "proof_command": "python -m pre_commit run -a",
      "safe_fix_outcome": "manual_success",
      "manual_fix_outcome": "merged",
      "pr_number": 1152,
      "merged": true,
      "time_to_green_seconds": 420
    }
  ]
}
```

Tests:

```bash
PYTHONPATH=src python -m pytest -q tests/test_investigation_outcome_memory.py
./scripts/pr_preflight.sh
```

---

## Phase 13 — Safe-fix candidate registry

### Goal

Publish candidate status for classes that may eventually become automatable.

### PR 13: Publish safe-fix candidate registry

Suggested branch:

```text
feature/safe-fix-candidate-registry
```

Suggested PR title:

```text
Publish safe-fix candidate registry
```

JSON contract:

```json
{
  "schema_version": "sdetkit.safe_fix.candidates.v1",
  "automation_allowed": false,
  "candidates": [
    {
      "candidate_key": "diagnosis:PRE_COMMIT_FORMAT_DRIFT",
      "category": "formatting",
      "risk_level": "low",
      "required_history_count": 3,
      "required_success_count": 3,
      "allowed_commands": ["python -m pre_commit run -a"],
      "forbidden_paths": [".github/workflows"],
      "rollback_required": true,
      "current_status": "OBSERVE_MORE"
    }
  ]
}
```

---

## Phase 14 — Auto-fix probation report

### Goal

Decide which candidates are not ready, need more observation, are blocked, or are ready for a policy PR.

### PR 14: Publish auto-fix probation report

Suggested branch:

```text
feature/auto-fix-probation-report
```

Suggested PR title:

```text
Publish auto-fix probation report
```

Statuses:

```text
NOT_READY
OBSERVE_MORE
READY_FOR_POLICY_PR
BLOCKED
```

---

## Phase 15 — Policy proposal generator

### Goal

Generate proposed policy changes when proof exists. Do not execute them.

### PR 15: Publish maintenance policy proposals

Suggested branch:

```text
feature/maintenance-policy-proposals
```

Suggested PR title:

```text
Publish maintenance policy proposals
```

Example output:

```markdown
# Maintenance policy proposal

## Proposal

Allow Ruff format drift to be fixed automatically in PR-only mode.

## Why

- 5 repeated reviewed successes
- no human edits after auto-format
- preflight passed every time

## Scope

- tests only
- no workflow files
- no security-sensitive files

## Required checks

- `python -m pre_commit run -a`
- `./scripts/pr_preflight.sh`

## Rollback

Required.
```

---

## Phase 16 — Auto-fix dry-run planner

### Goal

Show exact planned changes without modifying files.

### PR 16: Publish auto-fix dry-run plan

Suggested branch:

```text
feature/auto-fix-dry-run-plan
```

Suggested PR title:

```text
Publish auto-fix dry-run plan
```

Safety:

```text
no file writes
no commits
no PR creation
no allowlist expansion
```

---

## Phase 17 — Guarded PR-only auto-fix

### Goal

Enable auto-fix only for approved safe mechanical classes and only through PRs.

### PR 17: Enable guarded PR-only auto-fix

Suggested branch:

```text
feature/guarded-pr-auto-fix
```

Suggested PR title:

```text
Enable guarded PR-only auto-fix
```

Rules:

```text
never push directly to main
only approved candidate classes
only allowed commands
only allowed paths
must show diff
must run preflight
must attach proof
must open PR
must record outcome
```

---

## Phase 18 — Auto-fix outcome memory

### Goal

Record every guarded auto-fix attempt, success, failure, revert, human edit, and check outcome.

### PR 18: Record auto-fix outcome memory

Suggested branch:

```text
feature/auto-fix-outcome-memory
```

Suggested PR title:

```text
Record auto-fix outcome memory
```

Memory fields:

```json
{
  "schema_version": "sdetkit.auto_fix.outcome_memory.v1",
  "records": [
    {
      "candidate_key": "diagnosis:PRE_COMMIT_FORMAT_DRIFT",
      "attempted": true,
      "succeeded": true,
      "failed": false,
      "reverted": false,
      "human_edited": false,
      "checks_passed": true,
      "checks_failed": false,
      "pr_number": 1200
    }
  ]
}
```

---

## Command surfaces to add

Add commands gradually, only when the underlying shared modules exist.

```bash
python -m sdetkit investigate failure --log quality.log --format json
python -m sdetkit investigate failure --log quality.log --format markdown
python -m sdetkit investigate repo --root . --format json
python -m sdetkit investigate surface --root . --surface netclient --format json
python -m sdetkit investigate evidence --classification MISSING_PUBLIC_API_PARITY --surface netclient --out-dir build/investigate/netclient
```

Potential package entrypoint later:

```bash
sdetkit investigate failure --log quality.log --format markdown
sdetkit investigate repo --root . --format markdown
sdetkit investigate surface --root . --surface netclient --format markdown
```

---

## JSON and Markdown output conventions

Every roadmap artifact should follow these rules:

### JSON conventions

- Include `schema_version`.
- Include `diagnostic_only` when artifact is not allowed to mutate behavior.
- Include `automation_allowed` when relevant.
- Include stable keys for memory lookup.
- Use deterministic sorting for counts/maps.
- Include enough fields for downstream consumers.
- Avoid hidden behavior only present in code.

### Markdown conventions

- Start with a clear H1.
- Show safety state near the top.
- Include counts before details.
- Use compact tables for operator scanning.
- Include “What to do next” or equivalent.
- Include proof commands when actionable.
- Keep issue-comment sections truncation-safe.

---

## Safety boundaries

Strict safety rules for the whole roadmap:

```text
Product/API gaps stay review-first.
Broken test doubles stay review-first by default.
Runtime compatibility issues stay review-first.
Missing dependencies stay guidance/review-first.
Git branch drift stays command guidance.
Security findings stay review-first.
Unknown classifications stay review-first.
Auto-fix must never push directly to main.
Auto-fix must never broaden policy implicitly.
Auto-fix must never run without proof, policy, allowed commands, allowed paths, and PR-only guardrails.
```

---

## What stays diagnostic-only

These layers should remain diagnostic-only unless a later policy PR explicitly changes behavior:

- adaptive diagnosis classification
- failure investigation command
- repo investigation summary
- surface investigation summary
- parity detectors
- maintenance action categories
- proof checklist
- signal trends
- candidate registry
- probation report
- policy proposal generator
- dry-run planner
- PR/CI investigation summaries
- outcome memory recording

---

## What can become safe mechanical auto-fix later

Only narrow mechanical classes can become candidates, and only after proof/history/policy gates:

| Class | Candidate? | Notes |
|---|---:|---|
| `PRE_COMMIT_FORMAT_DRIFT` | yes | Only through pre-commit/formatters, PR-only, allowed paths |
| `RUFF_FIXABLE_LINT` | yes, narrow | Only approved Ruff fixable rules, PR-only, allowed paths |
| `GIT_BRANCH_DIVERGED` | no | Command guidance only |
| `REMOTE_BRANCH_DRIFT` | no | Sync guidance only |
| `MISSING_TEST_DEPENDENCY` | no | Dependency/environment guidance or explicit PR |
| `PYTHON_RUNTIME_COMPATIBILITY` | no | Compatibility PR required |
| `LOCAL_ENVIRONMENT_FRICTION` | no | Local guidance only |
| `BROKEN_TEST_DOUBLE` | no by default | Test behavior can be semantically wrong |
| `MISSING_PUBLIC_API_PARITY` | no | Product implementation required |
| `PRODUCT_LOGIC_FAILURE` | no | Product review required |
| `UNKNOWN_REVIEW_REQUIRED` | no | No automation until classified |

---

## How memory/history feeds recommendations

Memory should become the connective tissue of the system.

### Inputs to remember

- diagnosis class
- source surface
- affected files
- failure log hash or signature
- proof command
- proof result
- PR number
- merged/not merged
- checks passed/failed
- whether human edited the fix
- whether auto-fix was reverted
- time to green
- recurrence count
- last seen timestamp

### Consumers of memory

- recommendations
- priority rollups
- eligibility diagnostics
- action plans
- proof checklists
- category classifier
- signal trends
- candidate registry
- probation report
- policy proposals
- PR quality comments
- mission-control release bundles
- surface risk scoring

### Memory-driven promotion path

```text
first observation
  ↓
review required
  ↓
proof attached
  ↓
repeated successful evidence
  ↓
candidate later
  ↓
probation
  ↓
ready for policy PR
  ↓
dry run
  ↓
guarded PR-only auto-fix
  ↓
outcome memory
```

---

## First 5 PRs to execute

## 1. Expand adaptive diagnosis for local investigation failures

Branch:

```text
feature/adaptive-diagnosis-local-investigation-failures
```

Title:

```text
Expand adaptive diagnosis for local investigation failures
```

Why first:

- It upgrades the shared brain.
- It captures the real manual workflow.
- It prevents action categories/proof checklists from inventing separate classification logic.

---

## 2. Classify maintenance actions with adaptive diagnosis classes

Branch:

```text
feature/maintenance-action-diagnosis-categories
```

Title:

```text
Classify maintenance actions with adaptive diagnosis classes
```

Why second:

- Maintenance action plans need diagnosis classes.
- Later auto-fix safety depends on category.

---

## 3. Publish maintenance proof checklist

Branch:

```text
feature/maintenance-proof-checklist
```

Title:

```text
Publish maintenance proof checklist
```

Why third:

- Every future candidate needs explicit proof requirements.

---

## 4. Publish maintenance signal trend summary

Branch:

```text
feature/maintenance-signal-trends
```

Title:

```text
Publish maintenance signal trend summary
```

Why fourth:

- The system needs repeated-history strength before candidate/probation logic.

---

## 5. Add failure investigation command

Branch:

```text
feature/investigate-failure-command
```

Title:

```text
Add failure investigation command
```

Why fifth:

- Once the shared diagnosis brain is richer, expose it as a human-friendly command.

---

---

## GitHub Project board mapping

Use GitHub Project #2 as the execution board for this roadmap.

Recommended project name:

```text
SDETKit Adaptive Investigation Roadmap
```

### Recommended views

| View | Purpose | Group/sort by |
|---|---|---|
| Roadmap | Main execution board | Status |
| Phases | See roadmap progress by phase | Phase |
| Safety lane | Separate diagnostic-only work from future auto-fix work | Safety Route |
| PR queue | Track the next small PRs to execute | Priority, Status |
| Automation ladder | Track candidate/probation/policy/dry-run/auto-fix maturity | Safety Route |

### Recommended fields

| Field | Values |
|---|---|
| Status | Backlog, Ready, In Progress, In Review, Merged, Blocked, Later |
| Phase | Phase 1 through Phase 18 |
| Safety Route | Diagnostic Only, Review First, Safe Mechanical Candidate, Probation, Policy Proposal, Guarded PR Auto-Fix |
| Priority | P0, P1, P2 |
| Artifact Type | JSON, Markdown, CLI, Workflow, Memory, Policy, Tests |
| Depends On | Linked issue or PR |
| Proof Status | Missing, Partial, Complete, Not Required |
| Automation Status | Not Eligible, Observe More, Candidate Later, Ready for Policy PR, Blocked |
| Owner | Maintainer or automation lane owner |

### Suggested initial project issues

| Order | Issue title | Phase | Safety Route |
|---:|---|---|---|
| 1 | Expand adaptive diagnosis for local investigation failures | Phase 1 | Diagnostic Only |
| 2 | Classify maintenance actions with adaptive diagnosis classes | Phase 2 | Diagnostic Only |
| 3 | Publish maintenance proof checklist | Phase 3 | Diagnostic Only |
| 4 | Publish maintenance signal trend summary | Phase 4 | Diagnostic Only |
| 5 | Add failure investigation command | Phase 5 | Diagnostic Only |
| 6 | Add repository investigation summary | Phase 6 | Diagnostic Only |
| 7 | Add focused surface investigation | Phase 7 | Diagnostic Only |
| 8 | Detect public API parity gaps | Phase 8 | Review First |
| 9 | Write investigation candidate evidence | Phase 9 | Diagnostic Only |
| 10 | Route investigation diagnoses through safe-fix policy | Phase 10 | Review First |
| 11 | Publish investigation summaries for PR failures | Phase 11 | Diagnostic Only |
| 12 | Record investigation outcome memory | Phase 12 | Diagnostic Only |
| 13 | Publish safe-fix candidate registry | Phase 13 | Safe Mechanical Candidate |
| 14 | Publish auto-fix probation report | Phase 14 | Probation |
| 15 | Publish maintenance policy proposals | Phase 15 | Policy Proposal |
| 16 | Publish auto-fix dry-run plan | Phase 16 | Policy Proposal |
| 17 | Enable guarded PR-only auto-fix | Phase 17 | Guarded PR Auto-Fix |
| 18 | Record auto-fix outcome memory | Phase 18 | Guarded PR Auto-Fix |

### Board execution rules

- Keep only one or two P0 items in progress at a time.
- Do not move an item to `Ready` unless its dependency issue or PR is merged.
- Do not move any auto-fix item past `Probation` unless proof, trend, candidate registry, and policy proposal artifacts exist.
- Keep Phase 17 as a major milestone, not a near-term task. It should stay blocked until Phases 1-16 are stable.
- Every issue should include the safety route and whether behavior is diagnostic-only, review-first, or an approved mechanical candidate.

---

## Definition of done for every roadmap PR

Every PR in this roadmap should meet this checklist before merge.

### Required for every PR

```text
- PR scope is one small roadmap step.
- PR body explains why this step exists in the product spine.
- JSON schema is added or updated if the PR emits machine-readable output.
- Markdown output is added if the PR is operator-facing.
- Deterministic tests are added for every new diagnosis, policy, artifact, or command path.
- Existing behavior remains diagnostic-only unless the phase explicitly changes that.
- No auto-fix behavior is enabled unless the PR is a later policy-approved auto-fix phase.
- Rollback plan is included in the PR body.
- ./scripts/pr_preflight.sh passes.
```

### Extra requirements for workflow PRs

```text
- Workflow YAML is validated by pre-commit.
- Artifact upload paths are deterministic.
- Reporting steps use safe failure behavior when they must not create or mask CI failures.
- PR or maintenance comments stay truncation-safe.
- Comment sections are ordered so high-level diagnosis appears before low-level details.
```

### Extra requirements for diagnosis/classification PRs

```text
- Every new diagnosis class has at least one positive fixture.
- Unknown or ambiguous logs fall back to UNKNOWN_REVIEW_REQUIRED.
- Confidence is deterministic and explainable.
- Product/API/test/runtime/dependency/security/git-drift classes remain review-first.
- Only approved mechanical classes may set safe-to-auto-fix signals.
```

### Extra requirements for memory/history PRs

```text
- Records have stable IDs or stable memory lookup keys.
- Appends are idempotent where possible.
- Repeated-signal rollups are deterministic.
- Missing or malformed optional history files degrade safely.
- Memory never overrides safety policy without explicit proof and policy gates.
```

### Extra requirements for safe-fix or auto-fix PRs

```text
- The PR states the exact allowed commands.
- The PR states the exact allowed file/path scope.
- The PR states forbidden paths.
- The PR requires proof commands.
- The PR includes rollback behavior.
- The PR never pushes directly to main.
- The PR never mutates fork PRs.
- The PR records outcome memory.
```

---

## Major milestone gate for guarded auto-fix

Phase 17, guarded PR-only auto-fix, is a major milestone and must not start until the earlier investigation, proof, trend, candidate, probation, policy proposal, and dry-run layers are stable.

Before Phase 17 starts, the project should have:

```text
- Stable diagnosis classes for local investigation failures.
- Maintenance actions classified by diagnosis.
- Proof checklist artifacts.
- Signal trend artifacts.
- Investigation CLI front door.
- Repo and surface investigation summaries.
- Parity detectors.
- Investigation evidence writer.
- Safe-fix policy routing.
- PR/CI investigation summaries.
- Investigation outcome memory.
- Safe-fix candidate registry.
- Auto-fix probation report.
- Maintenance policy proposal generator.
- Auto-fix dry-run planner.
```

Only after those layers are proven should guarded PR-only auto-fix move from `Blocked` to `Ready`.


## Final roadmap line

```text
detect → diagnose → recommend → plan → prove → classify → trend → candidate → probation → policy proposal → dry run → guarded PR auto-fix → remember outcome
```

This is the product direction. Every PR should either strengthen one stage of this path or improve the evidence flow between stages.
