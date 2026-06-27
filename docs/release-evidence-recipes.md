# Release evidence recipes and sanitized proof samples

Use this page when a release owner or reviewer needs copy-ready commands for
release-readiness evidence, trusted PR Quality handoff evidence, or post-merge
verification.

These commands are **reporting-only**. They do not release, publish, merge,
apply patches, dismiss security findings, resolve review threads, or prove
semantic equivalence.

The report commands consume repository-local files. The post-merge command
does not collect GitHub evidence; collect and review the four saved evidence
files separately before invoking it.

## Recipe 1: baseline release-readiness package

### Inputs

- A clean local checkout at the commit being reviewed.
- The repository release surfaces, including `Makefile`,
  `.github/workflows/release.yml`, and the release evidence docs.

### Command

```bash
python -m sdetkit release-readiness-evidence-package \
  --root . \
  --out-json build/sdetkit/release-readiness-evidence/package.json \
  --out-md build/sdetkit/release-readiness-evidence/package.md \
  --format json
```

### Outputs

- `build/sdetkit/release-readiness-evidence/package.json`
- `build/sdetkit/release-readiness-evidence/package.md`

### Interpretation

A `ready_for_human_release_review` result means the expected evidence surfaces
were detected. It is not release or publish authorization. A
`review_required` result identifies missing or blocking evidence that a human
must resolve.

## Recipe 2: package a trusted PR Quality handoff

### Inputs

- A contributor-facing `pr-review-summary.md`.
- The matching trusted publisher `handoff-manifest.json`.
- Both files bound to the same Git head as the release package.

### Command

```bash
python -m sdetkit release-readiness-evidence-package \
  --root . \
  --pr-quality-summary evidence/pr-review-summary.md \
  --pr-quality-handoff-manifest evidence/handoff-manifest.json \
  --out-json build/sdetkit/release-readiness-evidence/package.json \
  --out-md build/sdetkit/release-readiness-evidence/package.md \
  --format json
```

### Outputs and review

Review `pr_quality_handoff.collection_status`, `head_matches`,
`release_review_blocking`, and `source_digests`. The summary and manifest are a
pair: supplying only one is `missing`, invalid JSON or authority fields are
`malformed`, a different head is `stale`, and mismatched bytes are
`digest_mismatch`.

## Recipe 3: post-merge verification from saved evidence

### Inputs

Create one deterministic evidence directory:

```text
evidence/
├── pr.json
├── main-status.json
├── review-threads.json
└── security-check.json
```

The directory must already contain reviewed GitHub and local-security evidence.
The command does not call GitHub and does not update those files.

### Command

```bash
python -m sdetkit post-merge-verification \
  --root . \
  --evidence-dir evidence \
  --previous-main-sha 1111111111111111111111111111111111111111 \
  --out-json build/sdetkit/post-merge-verification/report.json \
  --out-md build/sdetkit/post-merge-verification/report.md \
  --format json
```

### Outputs

- `build/sdetkit/post-merge-verification/report.json`
- `build/sdetkit/post-merge-verification/report.md`

### Interpretation

`verified` requires a closed merged PR, canonical merge containment, successful
CI, zero current GHAS review threads, zero warning/error security findings, and
no protected-path drift. Informational security findings remain visible through
`finding_count` and `info_count`; only `blocking_finding_count`, `warn_count`,
and `error_count` block verification.

## Recipe 4: verify freshness without regenerating

Release package:

```bash
python -m sdetkit release-readiness-evidence-package \
  --root . \
  --out-json build/sdetkit/release-readiness-evidence/package.json \
  --check-freshness \
  --format text
```

Post-merge report:

```bash
python -m sdetkit post-merge-verification \
  --root . \
  --evidence-dir evidence \
  --previous-main-sha 1111111111111111111111111111111111111111 \
  --out-json build/sdetkit/post-merge-verification/report.json \
  --check-freshness \
  --format text
```

A stale freshness result means the recorded schema, generator bytes, input
bytes, or Git head no longer matches the current context. Re-collect or
regenerate evidence only through the reviewed operator workflow.

## Outcome and collection-state matrix

| State | Meaning | Safe next action |
| --- | --- | --- |
| `collected` | The requested evidence parsed and passed its input contract. | Continue reviewing the report decision. |
| `missing` | A required file or paired input is absent. | Collect the missing evidence; do not infer zero. |
| `malformed` | Evidence exists but violates its JSON or field contract. | Repair the collection process and recollect. |
| `stale` | Evidence is bound to a different head or input state. | Recollect evidence for the current commit. |
| `digest_mismatch` | Trusted manifest bytes do not match the supplied summary. | Stop and restore the trusted publisher pair. |
| `review_required` | Evidence is readable but a human blocker remains. | Review missing items or blocking posture. |
| `unavailable` | A required collection or local Git relation is not authoritative. | Investigate collection access and retry read-only proof. |
| `verified` | Post-merge evidence satisfies the reporting contract. | Record closure; no additional authority is granted. |

## Sanitized proof samples

- [Release-readiness package sample](examples/release-readiness-evidence-package.sample.json)
- [Post-merge verification sample](examples/post-merge-verification.sample.json)

The samples use fixed timestamps, explicit `sha256-redacted` digest markers,
low-entropy placeholder commit SHAs, `example.invalid` URLs when a URL is
needed, and repository-relative paths.
They are examples, not current-run evidence.

## Troubleshooting

- **The report says missing:** verify the exact input filenames and paired
  arguments.
- **The report says malformed:** validate the top-level JSON object, schema, and
  strict authority boundary.
- **The report says stale:** compare the saved evidence head and input digests
  with the current checkout.
- **The post-merge report says review_required with info findings:** inspect
  `blocking_finding_count`; informational findings alone are non-blocking.
- **The report says unavailable:** do not convert the result to zero or
  success. Restore authoritative collection or local Git access.

## Authority boundary

Every recipe preserves:

```text
reporting_only=true
repo_mutation=false
issue_mutation_allowed=false
automation_allowed=false
patch_application_allowed=false
workflow_rerun_allowed=false
security_dismissal_allowed=false
release_authorized=false
publish_authorized=false
merge_authorized=false
semantic_equivalence_proven=false
```

Human review remains required for release, publish, merge, security dismissal,
and any repository mutation.
