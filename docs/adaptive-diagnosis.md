# Adaptive Diagnosis Intelligence

Adaptive Diagnosis turns raw quality evidence into an operator-facing diagnosis. For most operators, the preferred front door is `python -m sdetkit investigate failure`; use this module directly when you need to build or debug the diagnosis artifact itself. It is designed for the failure cases that are easy to miss in a large CI log: formatter drift after green tests, pytest failures hidden under summaries, repeated Mission Control failures, Doctor Cortex trend regressions, and adaptive-memory context that should change the recommendation.

The goal is not to print a fixed comment. Each diagnosis is composed from the evidence that was provided: the current log text, Mission Control output, ledger history, Doctor Cortex counts, and optional adaptive memory. The output explains what happened, why developers often miss it, what to fix first, which command proves the fix, and which learning signal should be carried forward.

## Safety and workflow position

Adaptive Diagnosis sits in the diagnostic part of the chain:

```text
detect -> diagnose -> recommend -> plan -> prove
```

Its JSON and Markdown outputs can recommend fixes and proof commands, but they are report-only by default. Later stages such as classify, trend, candidate, probation, policy proposal, dry run, guarded PR auto-fix, and remember outcome require explicit guarded workflow policy and review.

Use [Investigation operator guide](investigation-operator-guide.md) for day-to-day triage and [Artifact reference and generated sample map](artifact-reference.md) for uploaded artifact paths.

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

This keeps the system explainable while moving toward the larger SDETKit loop without making mutation the default:

```text
detect -> diagnose -> recommend -> plan -> prove -> classify -> trend -> candidate -> probation -> policy proposal -> dry run -> guarded PR auto-fix -> remember outcome
```

## Scenario packs and layered intelligence

The seeded adaptive scenario catalog is now a versioned data pack instead of an embedded Python-only table. The built-in pack lives at `src/sdetkit/data/adaptive_scenarios.json` and follows `schemas/adaptive-scenario-pack.schema.json`.

Each scenario must declare stable review fields: `code`, `title`, `signals`, `keywords`, `checks`, `commands`, `risk_band`, and `prior_weight`. Optional `odds` and `tags` fields let teams add confidence hints and governance labels without changing the diagnosis output contract.

Layering is deterministic:

1. SDETKit loads the built-in pack first.
2. A repository can add `.sdetkit/adaptive/scenarios.json` for repo-local scenarios.
3. Operators can set `SDETKIT_ADAPTIVE_SCENARIO_PACKS` to one or more `os.pathsep`-separated pack paths for organization or private overlays.
4. Later layers override earlier scenarios by `code`, and the final merged pack is sorted by code for stable output.

This keeps the default product useful on first run while allowing real teams to extend the brain with reviewable, schema-validated scenario data.

## Learning event loop

After writing an adaptive diagnosis JSON artifact, record it into the diagnosis learning JSONL database:

```bash
python -m sdetkit adaptive learn record build/adaptive-diagnosis.json \
  --db .sdetkit/adaptive-diagnosis-memory.jsonl \
  --format json
```

Summarize recurring scenarios and weak lanes:

```bash
python -m sdetkit adaptive learn summarize \
  --db .sdetkit/adaptive-diagnosis-memory.jsonl \
  --format json
```

Each learning event stores matched failure signals, candidate scenarios, the selected primary diagnosis marker, recommended checks, proof commands, recurrence count, and review placeholders for `proof_passed`, `fix_accepted`, and `false_positive`. The summarize command rolls those JSONL events into `top_recurring_scenarios` and `weakest_lanes` so follow-up work can prioritize the lanes causing repeated release friction.

### Outcome calibration

When operators have proof feedback, attach it while recording the learning event:

```bash
python -m sdetkit adaptive learn record build/adaptive-diagnosis.json \
  --db .sdetkit/adaptive-diagnosis-memory.jsonl \
  --proof-passed \
  --fix-accepted
```

Use `--proof-failed`, `--fix-rejected`, or `--false-positive` when the recommendation did not hold. The learning summary applies deterministic promotion/demotion rules: confirmed proof promotes confidence, false positives demote confidence, repeated recurrence increases risk, and thin evidence lowers confidence until better signals are available.

### Calibration-aware candidate ranking

Pass an adaptive learning summary back into diagnosis when you want local outcomes to influence candidate ordering:

```bash
PYTHONPATH=src python -m sdetkit.adaptive_diagnosis \
  --log build/quality.log \
  --adaptive-history build/adaptive-learning-summary.json \
  --format json \
  --out build/adaptive-diagnosis.json
```

When the summary contains `top_recurring_scenarios[].calibration`, promoted scenarios receive a ranking boost, false positives are demoted, recurrence can raise risk priority, and thin-evidence scenarios are kept lower until better signals exist. Unknown-review evidence includes a `candidate_calibration=` line whenever calibration affected a visible candidate.

## Unified failure intelligence bundle

Use the failure bundle when a CI log needs one operator handoff artifact instead of several manually stitched commands:

```bash
python -m sdetkit adaptive failure-bundle \
  --log build/quality.log \
  --out-dir build/sdetkit/failure-intelligence \
  --proof-failed \
  --format text
```

The bundle writes:

- `failure-intelligence-bundle.json`
- `adaptive-diagnosis.json`
- `adaptive-diagnosis-comment.md`
- `adaptive-diagnosis-memory.jsonl`
- `adaptive-learning-summary.json`
- `adaptive-safe-fix-plan.json`
- `adaptive-patch-plan.json`
- `operator-brief.json`
- `operator-brief.md`
- `artifact-manifest.json`

This command is still diagnostic and handoff-oriented. It does not apply fixes, create branches, push commits, or approve remediation. Known failure families become specific adaptive diagnoses; unknown failures remain review-first; green logs do not create fake adaptive blocks.

## Operator brief artifact

Generate the trust-grade handoff brief after gate, diagnosis, and optional learning artifacts exist:

```bash
python -m sdetkit adaptive brief \
  --gate build/gate-fast.json \
  --diagnosis build/adaptive-diagnosis.json \
  --learning-summary build/adaptive-learning-summary.json \
  --out build/sdetkit/operator-brief.md
```

The brief combines the gate result, adaptive diagnosis, candidate scenarios, candidate calibration, first proof command, safe-fix decision, and next owner action into one Markdown file for PR or release handoff.


### PR comment mode

Use compact PR comment mode when a bot should post a short, review-safe summary instead of the full operator brief:

```bash
python -m sdetkit adaptive brief \
  --gate build/gate-fast.json \
  --diagnosis build/adaptive-diagnosis.json \
  --format comment \
  --out build/sdetkit/operator-comment.md
```

Comment mode is intentionally concise: green runs avoid fake adaptive blocks, safe mechanical issues show a scoped guardrail path, and unknown failures stay review-first with candidate scenarios and the first proof command.
