# Cross-System Evidence Graph

The cross-system evidence graph is a read-only diagnostic artifact that normalizes release-confidence signals into one operator-facing view.

It connects:

```text
source -> finding -> risk surface -> owner files -> artifacts -> commands -> recurrence -> operator action
```

The first implementation is advisory only. It does not auto-fix, auto-commit, auto-push, auto-merge, weaken checks, or mark a change safe without proof.

## Inputs

The graph can consume existing SDETKit artifacts such as:

- Sentinel control-room JSON
- Mission Control JSON

The first supported command is:

```bash
python -m sdetkit.evidence_graph \
  --sentinel-control-room build/sdetkit/adaptive-sentinel/control-room.json \
  --mission-control build/sdetkit/mission-control/mission-control.json \
  --out-dir build/sdetkit/evidence-graph
```

Each input is optional. Missing inputs are reported in the source summary instead of failing the command.

## Outputs

The command writes:

```text
build/sdetkit/evidence-graph/evidence-graph.json
build/sdetkit/evidence-graph/evidence-graph.md
build/sdetkit/evidence-graph/evidence-graph-manifest.json
```

The JSON graph contains normalized nodes with:

```text
source
finding_id
title
summary
risk_surface
severity
review_first
safe_to_auto_fix
owner_files
source_artifacts
recommended_commands
proof_commands
recurrence_state
operator_action
automation_allowed_now
```

The Markdown report gives operators the active findings, owner files, artifacts, and exact commands to run next.

The manifest records the graph path, Markdown path, source summaries, node count, and the fixed advisory policy:

```text
automation_allowed_now=false
```

## Review-first policy

The graph preserves review-first boundaries for risky surfaces such as workflow, dependency, security, release, CLI, package, diagnostic-engine, and unknown findings.

If a source finding says `review_first=true`, the graph keeps the finding review-first and forces `safe_to_auto_fix=false`.

## Verification

Use focused proof before relying on a new graph change:

```bash
python -m pytest -q tests/test_evidence_graph.py -o addopts=
python -m pytest -q tests/test_adaptive_sentinel.py -o addopts=
python -m mypy src
python -m pre_commit run -a
```
