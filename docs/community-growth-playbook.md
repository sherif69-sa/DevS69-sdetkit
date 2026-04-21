# Community growth playbook (starter)

Use this lightweight playbook to turn product updates into repeatable community touchpoints.

## Posting cadence

- **1x/week:** one concrete workflow improvement (`before` -> `after`)
- **1x/week:** one artifact-driven use case from real usage
- **1x/month:** one roadmap + lessons learned update

## Post template: workflow win

```text
We used to make release calls with ad hoc checks.

Now we run:
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor

Result: deterministic ship/no-ship with JSON artifacts we can gate in CI.

If your team wants objective release confidence, this might help:
<repo-link>
```

## Post template: failure-to-fix narrative

```text
Today SDETKit caught a no-ship decision before release.

Signal:
- failed step: <step>
- artifact: <file>

Fix:
- <1-line remediation>

Why this matters: deterministic evidence made triage fast and non-arguable.

Repo:
<repo-link>
```

## Convert readers into contributors

- Add one `good first issue` per week with expected artifact output
- Link each issue to a specific contract/check
- Close the loop publicly when a contribution ships

## Metrics to track monthly

- Repo stars gained
- Unique contributors
- Issues opened by first-time users
- Time from issue -> first maintainer response

## If you are not using social media yet

Use a GitHub-native loop:

- Keep `docs/proof-log.md` updated with real outcomes
- Add links from proof entries to PRs/issues/workflows
- Ask users to submit `.github/ISSUE_TEMPLATE/value_proof_report.yml` entries
- Post short weekly release notes in GitHub Releases/Discussions
- Run `docs/proof-sprint-checklist.md` in 14-day cycles for consistent execution
