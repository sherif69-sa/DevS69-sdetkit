# Value proof reporting (1-minute guide)

Use this when SDETKit gave you a meaningful `ship` or `no-ship` decision and you want to share the result.

## Quick steps

1. Open the value-proof issue template:
   - <https://github.com/sherif69-sa/DevS69-sdetkit/issues/new?template=value_proof_report.yml>
2. Include deterministic artifact paths (`build/gate-fast.json`, `build/release-preflight.json`).
3. If decision was `no-ship`, include the first failing step.
4. Add what action you took and what happened after rerun.
5. If available, include adaptive reviewer `judgment_summary` and confidence.

## What makes a strong proof report

- Concrete context (PR/release scope)
- Artifact-backed signal (not only narrative)
- Remediation + rerun outcome
- Link to PR/issue/workflow run if available

## Why this matters

Proof reports help maintainers and new users:

- validate real-world value quickly,
- spot recurring friction patterns,
- improve docs, defaults, and operator UX based on evidence.
