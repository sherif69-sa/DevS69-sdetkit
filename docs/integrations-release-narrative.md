# Release narrative (Day 20)

Day 20 translates release readiness evidence into non-maintainer changelog storytelling.

## Who should run Day 20

- Maintainers writing release notes for mixed technical/non-technical audiences.
- Developer advocates preparing community launch posts.
- Product and support teams aligning on what changed and why it matters.

## Story inputs

- Day 19 release-readiness summary (`release_score`, `gate_status`, recommendations).
- Changelog highlights for user-visible updates.

## Fast verification commands

```bash
python -m sdetkit release-narrative --format json --strict
python -m sdetkit release-narrative --emit-pack-dir docs/artifacts/day20-release-narrative-pack --format json --strict
python -m sdetkit release-narrative --execute --evidence-dir docs/artifacts/day20-release-narrative-pack/evidence --format json --strict
python scripts/check_day20_release_narrative_contract.py
```

## Execution evidence mode

`--execute` runs the Day 20 command chain and writes deterministic logs into `--evidence-dir`.

## Narrative channels

- Release notes (maintainer + product audiences)
- Community post (social + discussion channels)
- Internal weekly update (engineering + support)

## Storytelling checklist

- [ ] Outcome-first summary is present.
- [ ] Risks and follow-ups are explicit.
- [ ] Validation evidence is linked.
- [ ] Audience-specific blurbs are generated.
