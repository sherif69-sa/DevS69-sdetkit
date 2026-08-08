# Workflow permission review session

Workflow Permission Review Session v1 is the batch human-review layer above the exact review packets and below Decision Record v1.

It exists to make reviewing a permission queue operationally practical without letting software choose the answer.

## Product flow

```text
workflow-governance-report
  -> permission review control plane
  -> exact review packet bundle
  -> human review session
  -> individually validated Decision Record v1 files
  -> separate permission-only implementation PRs
  -> workflow-specific execution proof + rollback
```

The session compiler never edits workflow YAML, never changes a permission, never commits a decision, never opens an implementation PR, never merges anything, and never infers `keep | reduce | split | defer`.

## Generate a complete-session template

```bash
python -m sdetkit.workflow_permission_review_session \
  --root . \
  --template-mode complete \
  --template-out build/sdetkit/workflow-permission-review-session.json \
  --format text
```

A complete template contains one entry for every currently pending review packet. Immutable packet bindings are prefilled; human fields are not.

At session level the reviewer must supply:

- `reviewer`;
- `reviewer_evidence` as a GitHub URL;
- timezone-aware `decided_at`.

For each reviewed packet the human must supply:

- `decision`: `keep`, `reduce`, `split`, or `defer`;
- `rationale`;
- `proposed_change` using the Decision Record v1 rules;
- `proof_acknowledged: true`;
- `rollback_acknowledged: true`.

The software does not default any of these fields.

## Partial versus complete sessions

`partial` means the reviewer intentionally submits one or more reviewed pending packets. Omitted packets remain pending.

`complete` means every currently pending packet must appear exactly once. Missing or duplicate review IDs block the entire compilation.

A partial session is not silently upgraded to complete, and a complete session is not silently downgraded to partial.

## Exact freshness binding

The session is bound to:

- the packet bundle digest;
- the packet-layer input digest;
- each review ID;
- each packet digest;
- each workflow path;
- each workflow SHA-256;
- each permission group.

If the packet bundle or any reviewed packet changes after the session was prepared, validation returns `stale` and compilation emits zero Decision Record v1 files.

## Fail-closed compilation

Validate and compile a completed session:

```bash
python -m sdetkit.workflow_permission_review_session \
  --root . \
  --session build/sdetkit/workflow-permission-review-session.json \
  --compile-out-dir build/sdetkit/workflow-permission-decisions \
  --fail-on-invalid \
  --format text
```

Every candidate is reconstructed from the current packet binding plus the human-entered session fields and passed through the Decision Record v1 validator.

If any session-level or entry-level requirement fails, the compiler returns `blocked` and emits zero records.

For a valid current session the compiler writes only to the explicitly requested output directory and creates:

- one `*.decision.json` candidate per reviewed packet;
- `workflow-permission-review-session-compilation.json` with session digest, packet bundle digest, record SHA-256 values, and a zero-authority boundary.

These are candidate review artifacts. They are not automatically copied to `docs/ci/workflow-permission-decisions/`.

## Source-tree write guard

When the output path is inside the repository, compiled candidates may only be written under `build/`.

The compiler refuses repository-local destinations such as:

- `docs/ci/workflow-permission-decisions/`;
- `.github/workflows/`;
- `src/`;
- arbitrary repository folders.

This prevents the batch-review tool from turning human input into an unreviewed repository mutation.

## Decision Record v1 remains authoritative

Review Session v1 does not replace Decision Record v1. It is a batch input and compilation envelope.

Each compiled record must independently pass the existing Decision Record v1 rules, including exact workflow digest, permission group, reviewer evidence, rationale, decision-specific proposed change, proof contract, rollback contract, and zero implementation authority.

## No implementation authority

A valid session proves only that human decision data is current and structurally valid.

It does **not** prove that a future permission reduction is correct. `reduce` and `split` still require a separate reviewed implementation PR with workflow-specific runtime proof and rollback.

## Recommended review workflow

1. Generate the latest Stage 4 packet bundle.
2. Generate a fresh Stage 5 session template.
3. Review the packet Markdown/JSON for each chosen workflow.
4. Fill only the human fields you personally reviewed.
5. Run validation with `--fail-on-invalid`.
6. Compile candidates under `build/`.
7. Inspect the compilation manifest and each Decision Record v1 candidate.
8. Only after explicit repository review, separately retain approved decision records.
9. Build permission-only implementation PRs from those approved decisions.

## Authority boundary

The session layer hard-codes false for:

- automation authority;
- commit authority;
- decision inference;
- human-decision fabrication;
- implementation authority;
- merge authority;
- patch application;
- permission mutation;
- security dismissal;
- semantic equivalence;
- source-tree writes;
- workflow mutation.

The compiler can prepare evidence. It cannot decide or implement.
