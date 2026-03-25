# Release communications

Release communications translates release-readiness evidence into non-maintainer changelog storytelling.

## Who should run release-communications

- Maintainers writing release notes for mixed technical/non-technical audiences.
- Developer advocates preparing community launch posts.
- Product and support teams aligning on what changed and why it matters.

## Story inputs

- Release-readiness summary (`release_score`, `gate_status`, recommendations).
- Changelog highlights for user-visible updates.

## Fast verification commands

```bash
python -m sdetkit release-communications --format json --strict
python -m sdetkit release-communications --emit-pack-dir docs/artifacts/release-communications-pack --format json --strict
python -m sdetkit release-communications --execute --evidence-dir docs/artifacts/release-communications-pack/evidence --format json --strict
python scripts/check_day20_release_narrative_contract.py
```

## Execution evidence mode

`--execute` runs the release-communications command chain and writes deterministic logs into `--evidence-dir`.

## Narrative channels

- Release notes (maintainer + product audiences)
- Community post (social + discussion channels)
- Internal weekly update (engineering + support)

## Storytelling checklist

- [ ] Outcome-first summary is present.
- [ ] Risks and follow-ups are explicit.
- [ ] Validation evidence is linked.
- [ ] Audience-specific blurbs are generated.
