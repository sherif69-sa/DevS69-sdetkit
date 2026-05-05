# Adaptive Diagnosis Intelligence

Adaptive Diagnosis turns raw quality evidence into an operator-facing diagnosis. It is designed for the failure cases that are easy to miss in a large CI log: formatter drift after green tests, pytest failures hidden under summaries, repeated Mission Control failures, Doctor Cortex trend regressions, and adaptive-memory context that should change the recommendation.

The goal is not to print a fixed comment. Each diagnosis is composed from the evidence that was provided: the current log text, Mission Control output, ledger history, Doctor Cortex counts, and optional adaptive memory. The output explains what happened, why developers often miss it, what to fix first, which command proves the fix, and which learning signal should be carried forward.

## Run it locally

Use the module directly when you have one or more evidence files:

```bash
PYTHONPATH=src python -m sdetkit.adaptive_diagnosis \
  --log build/quality.log \
  --ledger .sdetkit/runs/mission-control-runs.jsonl \
  --mission-control build/mission-control/mission-control.json \
  --adaptive-history build/adaptive/history.json \
  --format md \
  --out build/adaptive-diagnosis.md
```

All inputs are optional. When an input is missing, the engine still emits a safe result from the evidence it has.

For machine-readable output:

```bash
PYTHONPATH=src python -m sdetkit.adaptive_diagnosis \
  --log build/quality.log \
  --format json \
  --out build/adaptive-diagnosis.json
```

For compact terminal output:

```bash
PYTHONPATH=src python -m sdetkit.adaptive_diagnosis --log build/quality.log
```

## Output fields

The JSON output uses schema version `sdetkit.adaptive.diagnosis.v1`.

| Field | Meaning |
| --- | --- |
| `ok` | True when the result is clear or only needs monitoring. |
| `status` | One of `clear`, `monitor`, `needs_attention`, or `needs_fix`. |
| `risk_score` | Bounded 0-100 score based on severity, confidence, and repeat count. |
| `confidence` | Overall confidence across detected diagnoses. |
| `summary` | One-line operator summary. |
| `diagnosis_count` | Number of diagnosis entries emitted. |
| `diagnoses` | Evidence-fitted diagnosis entries. |
| `fix_plan` | Ranked first actions and proof commands for the top diagnoses. |
| `learning_updates` | Signals that later automation can feed into adaptive memory. |

Each diagnosis contains:

| Field | Meaning |
| --- | --- |
| `code` | Stable diagnosis code, such as `PRE_COMMIT_FORMAT_DRIFT`. |
| `severity` | `high`, `medium`, `low`, or `info`. |
| `confidence` | `high`, `medium`, or `low`. |
| `title` | Short operator-facing title. |
| `diagnosis` | What happened and what it likely means. |
| `why_developers_miss_it` | The hidden-risk explanation. |
| `evidence` | Sanitized evidence snippets that triggered the diagnosis. |
| `recommended_fix` | Smallest recommended repair steps. |
| `proof_commands` | Commands to prove the fix. |
| `risk_if_ignored` | Consequence of leaving the issue unresolved. |
| `learning_signal` | Stable signal name for future adaptive workflows. |
| `repeat_count` | Historical recurrence count when available. |
| `affected_files` | Sanitized file mentions, when the log identifies files. |

## Diagnosis examples

### Formatter drift after tests pass

A log with `ruff format` failure, `files were modified by this hook`, and green pytest evidence produces `PRE_COMMIT_FORMAT_DRIFT`.

This is intentionally different from a behavior failure. The operator guidance should say that the implementation may already be correct, but CI is blocked because pushed files did not match formatter output.

Typical proof command:

```bash
PYTHONPATH=src python -m ruff format --check <touched-python-files>
```

### Pytest assertion failure

A log with a failing test such as `FAILED tests/test_widget.py::test_widget_contract` produces `PYTEST_ASSERTION_FAILURE`.

The diagnosis points at the first failing test instead of asking for a full-suite rerun first. This keeps the fix focused on the behavior mismatch.

Typical proof command:

```bash
PYTHONPATH=src python -m pytest -q tests/test_widget.py::test_widget_contract
```

### Pytest import or collection failure

Import failures are treated as high severity because the suite may stop before exercising the behavior under review. The guidance should direct the operator to the first import traceback and the affected module.

### Mission Control no-ship

A Mission Control payload with `decision=NO_SHIP`, failed steps, or a nonzero failed-step count produces `MISSION_CONTROL_NO_SHIP`.

This diagnosis exists because developers often inspect one failing command and miss the higher-level release decision that combines multiple evidence sources.

### Repeated release friction

Ledger history with repeated `NO_SHIP` decisions or repeated failed runs produces `MISSION_CONTROL_REPEATED_FAILURE_PATTERN`.

This is one of the main adaptive benefits: a single CI run can look like a one-off failure, while the ledger shows that the same release friction keeps returning.

### Doctor Cortex regression

When the latest two Doctor-enabled ledger entries show higher diagnosis or prescription counts, the engine emits one or both of:

- `DOCTOR_CORTEX_DIAGNOSIS_REGRESSION`
- `DOCTOR_CORTEX_PRESCRIPTION_REGRESSION`

These diagnoses catch cases where the current run may look acceptable, but diagnostic or remediation load is increasing over time.

### Adaptive memory context

When adaptive memory is empty, the engine emits `LEARNING_DB_EMPTY`. When it contains prior runs, it emits `KNOWN_ADAPTIVE_PATTERN_AVAILABLE`.

The point is to distinguish "first-time investigation" from "use the memory we already built." Future integrations can use the `learning_updates` payload to decide what gets written back into adaptive memory.

## Public-safety behavior

Adaptive Diagnosis output is operator-facing and should not leak raw runner paths, private workspace paths, token-like fixtures, or full command logs. Evidence and file mentions are sanitized before they are emitted.

The expected pattern is:

```text
raw evidence in, safe diagnosis out
```

That makes the Markdown suitable for CI artifacts and future PR comments.

## How to use the result

Start with the first diagnosis entry. Diagnoses are sorted by severity, confidence, repeat count, and code. The top entry is the most important operator action.

Use the `recommended_fix` list for the smallest repair path. Use `proof_commands` to verify the branch after the repair. Use `learning_updates` to understand what future adaptive memory or autopilot integrations should remember.

## Integration roadmap

The standalone engine is intentionally separate from the automations that will call it. The recommended rollout is:

1. Keep the engine deterministic and tested.
2. Write Adaptive Diagnosis JSON and Markdown artifacts from maintenance autopilot.
3. Add an Adaptive Diagnosis summary to PR Quality Comment.
4. Feed learning signals into adaptive memory.
5. Add a safe fix planner for narrow cases such as format-only or import-order-only repairs.

This keeps the system explainable while moving toward the larger SDETKit loop:

```text
find -> diagnose -> recommend -> prove -> learn -> safely fix
```
