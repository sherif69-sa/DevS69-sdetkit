# Workflow permission review packet

`python -m sdetkit.workflow_permission_review_packet` turns the workflow permission review control plane into a deterministic reviewer bundle.

The bundle is evidence-only. It does not create a human decision, recommend `keep | reduce | split | defer`, edit workflow YAML, authorize a permission change, authorize a patch, authorize merge, dismiss security findings, or claim semantic equivalence.

## Why this layer exists

The control plane identifies what needs human review. Decision Record V1 defines how a real human decision is recorded. The review-packet layer fills the operational gap between those two stages by preparing the evidence a reviewer needs without crossing the human-decision boundary.

The intended flow is:

```text
workflow-governance-report
  -> workflow permission review control plane
  -> workflow permission review packet
  -> human reviewer
  -> exact decision record v1
  -> separate permission-only implementation PR
  -> workflow-specific proof + rollback
```

## Generate the complete bundle

```bash
python -m sdetkit.workflow_permission_review_packet \
  --root . \
  --out-dir build/sdetkit/workflow-permission-review-packets \
  --format text
```

The output directory contains:

- `workflow-permission-review-packet-index.json`;
- `workflow-permission-review-packet-index.md`;
- one exact-digest JSON packet per review item;
- one reviewer-readable Markdown packet per review item.

The packet filenames use the stable review ID, not a mutable display title.

## What every packet contains

Each generated packet retains:

- review ID;
- workflow path;
- exact workflow SHA-256;
- permission group;
- current write scopes;
- inferred permission reasons from the governance report;
- human evidence still required;
- retained review-card and decision-evidence references when present;
- transparent triage signals derived from the current write scopes;
- allowed human decision enum;
- proof contract;
- rollback contract;
- a blank Decision Record V1 template;
- a zero-authority boundary.

The packet digest is computed over canonical JSON for the complete packet except the digest field itself.

## Triage signals are not recommendations

The generator records transparent signals such as whether a workflow contains `contents: write`, `security-events: write`, `id-token: write`, or more than one write scope.

Those signals are descriptive only. They do not produce a risk verdict, recommendation, decision, or permission change. The generated field `machine_recommendation` is always `null`.

## Blank decision template

For a queue item that does not yet have a valid current human decision, the packet contains a template with the exact immutable binding fields pre-populated:

- `review_id`;
- `workflow`;
- `workflow_sha256`;
- `permission_group`;
- proof contract;
- rollback contract;
- zero-authority boundary.

The human fields remain empty:

- `decision`;
- `reviewer`;
- `reviewer_evidence`;
- `decided_at`;
- `rationale`;
- `proposed_change`.

The template is intentionally not a valid decision record until a human reviewer completes it and records the evidence required by Decision Record V1.

## Freshness validation

After retaining an index, validate it against the current repository:

```bash
python -m sdetkit.workflow_permission_review_packet \
  --root . \
  --check-index build/sdetkit/workflow-permission-review-packets/workflow-permission-review-packet-index.json \
  --fail-on-stale \
  --format text
```

Freshness is bound to:

- the packet-generator source;
- `docs/contracts/workflow-permission-review-packet.v1.json`;
- the exact control-plane input digest.

The control-plane digest already transitively binds workflow bytes, review evidence, decision evidence, Decision Record V1, and its own generator/contract inputs. Therefore workflow/evidence/decision changes make retained packet output stale.

## Existing review cards

Human-authored review cards remain evidence, not generated truth. The packet generator maps a retained card to a workflow when the card names the workflow or its permission group. It does not parse prose into a decision.

This preserves scoped documents such as the Pages review card and the PR/issue-interaction card without treating their text as automatic permission authority.

## Proof before merge

For changes to this product surface, run at minimum:

```bash
python -m ruff check \
  src/sdetkit/workflow_permission_review_packet.py \
  tests/test_workflow_permission_review_packet.py
python -m mypy \
  src/sdetkit/workflow_permission_decision_record.py \
  src/sdetkit/workflow_permission_review_control_plane.py \
  src/sdetkit/workflow_permission_review_packet.py
python -m pytest -q \
  tests/test_workflow_permission_decision_record.py \
  tests/test_workflow_permission_review_control_plane.py \
  tests/test_workflow_permission_review_packet.py \
  tests/test_quality_truth_baseline.py \
  -o addopts=
```

Then require the repository's normal exact-head Quality, CI, Security/CodeQL, cross-platform, release-qualification, and PR-quality gates.

## Authority boundary

A review packet cannot make a future permission-only PR safe by itself. Even after a human decision is recorded, implementation remains a separate reviewed change with workflow-specific execution proof and rollback.
