# Release communications report

## Release communications report

Release communications provides a deterministic **release narrative operating lane** that converts release-readiness posture and changelog highlights into reusable multi-channel storytelling with strict contract validation.

## What shipped

- Added `sdetkit release-narrative` CLI to build non-maintainer narratives from release-readiness summary evidence and changelog bullets.
- Added strict docs contract checks (required sections + commands), minimum-score gates, and a score/failure model similar to reliability-evidence and release-readiness enforcement.
- Added execution evidence mode (`--execute`) with deterministic command logs and summary JSON.
- Expanded emit-pack outputs to include summary JSON, narrative markdown, audience blurbs, narrative channels, and validation commands.

## Validation commands

```bash
python -m sdetkit release-narrative --format text
python -m sdetkit release-narrative --format json --strict
python -m sdetkit release-narrative --emit-pack-dir docs/artifacts/release-communications-pack --format json --strict
python -m sdetkit release-narrative --execute --evidence-dir docs/artifacts/release-communications-pack/evidence --format json --strict
python -m sdetkit release-narrative --format markdown --output docs/artifacts/release-communications-sample.md
python scripts/check_day20_release_narrative_contract.py
```

## Closeout

Release communications now provides one strict and auditable narrative lane: release story, channel-ready blurbs, validation commands, and execution evidence that can be reused across release notes, social distribution, and internal status updates.
