# SDETKit proof log

This log is a lightweight, GitHub-native way to show real value over time.

## How to use this log

- Add one entry whenever SDETKit produced a meaningful ship/no-ship decision.
- Keep it short and factual.
- Link the PR/issue/run when possible.

## Entry template

```md
### YYYY-MM-DD — <short title>
- Context: <what was being changed/released>
- Signal: <ship/no-ship + failing step if any>
- Artifact(s): <path(s)>
- Action taken: <what changed>
- Outcome: <result after rerun>
- Link: <PR/issue/workflow URL>
```

## Recent entries

### 2026-04-21 — README conversion pass for first-star growth
- Context: improve first-time visitor conversion while keeping deterministic onboarding.
- Signal: ship (docs-only change with tests passing).
- Artifact(s): `README.md`, `docs/community-growth-playbook.md`.
- Action taken: tightened first-screen messaging, added live signals, simplified navigation.
- Outcome: faster scan path for new users and clearer star CTA.
- Link: `git log --oneline` on current branch.
