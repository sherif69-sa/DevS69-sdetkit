# Team rollout scenario (local trial → CI pilot → release gate)

**Use this page if:** you want a realistic staged scenario for organizational rollout conversations.

**Canonical rollout instructions remain in:** [Adoption](adoption.md) and [Recommended CI flow](recommended-ci-flow.md).

This is a recommended adoption flow based on SDETKit's current repository workflows and docs.

It is a scenario, not a claim that a specific company already executed it.

## Stage 0 — one engineer proves value locally (impact 1)

Commands:

```bash
python -m sdetkit doctor
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
```

Exit criteria:

- Team can run commands locally.
- `build/gate-fast.json` exists and can be shared in a PR comment.

## Stage 1 — CI pilot on pull requests (week 1)

Add one CI job using:

```bash
python -m sdetkit gate fast
```

Exit criteria:

- PRs consistently produce pass/fail results.
- Engineers use `failed_steps` to triage first, logs second.

## Stage 2 — introduce policy budgets (week 2)

Add strict thresholds incrementally:

```bash
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0 --out build/security-enforce.json
```

If initial `--max-info 0` is too strict, set a temporary baseline and ratchet down over time.

Exit criteria:

- Security budget failures are explicit and reviewable in JSON.
- Team agrees on ratchet plan and owners.

## Stage 3 — release lane enforcement (week 3+)

Enable release preflight in release branches/tags:

```bash
python -m sdetkit gate release --format json --stable-json --out build/release-preflight.json
```

Exit criteria:

- Release decisions reference `build/release-preflight.json` plus supporting gate artifacts.
- Handoffs include artifact links instead of only terminal snippets.

## Operating rhythm after rollout

- **PR lane:** keep `gate fast` always on.
- **Main/release lane:** enforce security budgets and `gate release`.
- **Incident/failure triage:** use artifact-first flow from [CI artifact walkthrough](ci-artifact-walkthrough.md).

## Anti-patterns to avoid

- Enabling all strict thresholds at once without baseline discussion.
- Treating first non-green run as tool failure instead of integration backlog.
- Reviewing logs before reading structured artifacts.

## Related rollout docs

- [Adopt SDETKit in your repository](adoption.md)
- [Recommended CI flow](recommended-ci-flow.md)
- [Adoption troubleshooting](adoption-troubleshooting.md)
- [CI artifact walkthrough](ci-artifact-walkthrough.md)
