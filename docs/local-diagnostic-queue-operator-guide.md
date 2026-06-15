# Local diagnostic queue operator guide

Use this guide to run the bounded local diagnostic worker queue after the evidence inputs for one or more diagnostic jobs already exist.

This capability is local, deterministic, and review-first. It does not use a hosted queue, start a background service, run proof commands, apply patches, publish a PR decision, or authorize a merge.

## Operator contract

The local queue path connects these accepted contracts:

```text
DiagnosticJob
  -> deterministic file-backed queue
  -> bounded queue runner
  -> read-only diagnostic worker
  -> diagnostic vector
  -> reporting-only trajectory artifacts
  -> completed or failed queue record
```

The runner processes at most the explicit `--max-jobs` value.

It stops when:

- no pending jobs remain;
- the maximum job count is reached; or
- the first attempted job fails.

Failed jobs are not retried automatically. Later pending jobs remain pending after the first failure.

## Required inputs

The CLI requires:

| Argument | Meaning |
| --- | --- |
| `--queue-path` | Local JSON queue file. |
| `--out-root` | Root directory for worker output artifacts. |
| `--input-root` | Root directory used to resolve relative evidence paths declared by jobs. |
| `--max-jobs` | Required positive integer bound. |
| `--claimed-at` | Explicit deterministic claim timestamp. |
| `--finished-at` | Explicit deterministic completion or failure timestamp. |

Each queued `DiagnosticJob` must declare at least one supported evidence input:

- `check_intelligence`
- `evidence_graph`
- `pr_quality_action_report`
- `security_review`
- `runtime_proof_artifacts`

Relative evidence paths are resolved from `--input-root`.

## Create a local queue

The following example creates one job using an existing check-intelligence artifact:

```bash
mkdir -p build/local-diagnostic-queue/inputs

cp build/check-intelligence.json   build/local-diagnostic-queue/inputs/check-intelligence.json

python - <<'PYTHON'
from pathlib import Path

from sdetkit.diagnostic_job import build_diagnostic_job
from sdetkit.job_queue import enqueue_job

root = Path("build/local-diagnostic-queue")
queue_path = root / "queue.json"

job = build_diagnostic_job(
    repo="owner/repository",
    base_sha="BASE_SHA",
    head_sha="HEAD_SHA",
    event_name="pull_request",
    pr_number=123,
    input_artifacts={
        "check_intelligence": "check-intelligence.json",
    },
    generated_at="2026-06-15T00:00:00Z",
)

enqueue_job(
    queue_path,
    job,
    enqueued_at="2026-06-15T00:00:00Z",
)

print(queue_path)
print(job["job_id"])
PYTHON
```

Replace the repository identity, commit SHAs, PR number, and timestamps with explicit values from the evidence being inspected.

## Run the bounded queue

Use the installed command:

```bash
sdetkit-diagnostic-queue-runner   --queue-path build/local-diagnostic-queue/queue.json   --out-root build/local-diagnostic-queue/worker   --input-root build/local-diagnostic-queue/inputs   --max-jobs 1   --claimed-at 2026-06-15T01:00:00Z   --finished-at 2026-06-15T02:00:00Z
```

The equivalent Python module command is:

```bash
python -m sdetkit.diagnostic_queue_runner_cli   --queue-path build/local-diagnostic-queue/queue.json   --out-root build/local-diagnostic-queue/worker   --input-root build/local-diagnostic-queue/inputs   --max-jobs 1   --claimed-at 2026-06-15T01:00:00Z   --finished-at 2026-06-15T02:00:00Z
```

The CLI prints a deterministic JSON summary to standard output.

## Exit codes

| Exit code | Meaning |
| --- | --- |
| `0` | The bounded run completed without a job failure. This includes an empty queue. |
| `1` | A runner or job failure occurred. Inspect the JSON summary and persisted queue record. |
| `2` | CLI usage error, such as a missing required argument or invalid `--max-jobs`. |

A successful process exit does not authorize mutation or merge. It only means the bounded local queue operation completed according to its contract.

## Queue states

Each queue record is in one of these states:

```text
pending -> claimed -> completed
                   -> failed
```

A completed record contains claim and completion timestamps plus result-artifact paths.

A failed record contains claim and failure timestamps plus a sanitized failure reason. It contains no completion artifacts.

## Output artifacts

For a completed job, inspect:

```text
<out-root>/<job-id>/diagnostic-worker-result.json
<out-root>/<job-id>/vector/diagnostic-vector.json
<out-root>/<job-id>/trajectory/diagnostic-worker-trajectory.jsonl
<out-root>/<job-id>/trajectory/diagnostic-worker-trajectory-summary.json
<out-root>/<job-id>/trajectory/diagnostic-worker-trajectory.md
```

The completed queue record also contains these artifact references.

The trajectory output is reporting-only:

```text
reporting_only=true
current_pr_decision_input=false
automation_allowed=false
patch_application_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
```

Do not present trajectory observations as focused proof, CI proof, patch approval, or merge approval.

## Read the JSON summary

Read these fields first:

- `status`
- `stop_reason`
- `max_jobs`
- `jobs_attempted`
- `jobs_completed`
- `jobs_failed`
- `failure`
- `queue_state_counts`
- `decision_boundary`
- `execution`

Expected stop reasons are:

- `no_pending_jobs`
- `max_jobs_reached`
- `job_failed`

## Failure handling

When `status` is `failed`:

1. Read `failure.job_id`.
2. Read `failure.exception_type` and `failure.message`.
3. Inspect that job in the queue JSON.
4. Confirm later jobs remain `pending`.
5. Correct the evidence input or create a new reviewed job.
6. Do not edit a failed record back to `pending`.
7. Do not assume an automatic retry occurred.

A missing declared evidence input is a job failure, not an empty evidence result.

## Safety boundary

The local queue runner does not:

- run repository proof commands;
- change source files;
- apply patches;
- retry failed jobs;
- create or update pull requests;
- dismiss security findings;
- publish a current-PR decision;
- authorize merge;
- provide semantic-equivalence proof;
- use cloud or external queue infrastructure.

## Verification

Run the real subprocess end-to-end contract:

```bash
python -m pytest -q   tests/test_diagnostic_queue_runner_e2e.py   -o addopts=
```

Run the focused local queue contract suite:

```bash
python -m pytest -q   tests/test_diagnostic_queue_runner_e2e.py   tests/test_diagnostic_queue_runner_cli.py   tests/test_diagnostic_queue_runner.py   tests/test_queued_diagnostic_worker.py   tests/test_diagnostic_worker_trajectory.py   tests/test_job_queue.py   tests/test_diagnostic_job.py   -o addopts=
```

Then run the repository quality proof:

```bash
make proof-after-format
```

If the proof command changes a generated roadmap manifest that this documentation PR does not own, restore that generated file before staging the documentation changes.
