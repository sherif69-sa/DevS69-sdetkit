# Before/after evidence example

Use this page to compare release review behavior before and after adopting deterministic evidence artifacts.

For first-time onboarding, start with [Start here](index.md) and [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md).

## Before: ad hoc checks and log-only evidence

Typical flow in many repos:

```bash
ruff check .
pytest -q
bandit -q -r src
```

What often happens:

- Different engineers run different sequences.
- Logs are long and mixed; reviewers scroll to find root cause.
- CI failures are hard to compare between runs.
- Release decisions rely on screenshots or pasted snippets.

## After: deterministic gates + structured evidence

SDETKit flow:

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0 --out build/security-enforce.json
python -m sdetkit gate release --format json --stable-json --out build/release-preflight.json
```

Evidence files produced:

```text
build/
├── gate-fast.json
├── security-enforce.json
└── release-preflight.json
```

Representative real shapes documented in this repository:

- `gate-fast.json` includes `ok`, `profile`, `failed_steps`.
- `security-enforce.json` includes `ok`, `counts`, `exceeded`.
- `release-preflight.json` includes `ok`, `profile`, `failed_steps`.

See exact examples in [Evidence showcase](evidence-showcase.md).

## What this changes in practice

| Decision step | Before (log-only) | After (SDETKit evidence) |
| --- | --- | --- |
| First triage move | Read mixed console output | Open JSON artifact and check `ok` + first failed key |
| Policy traceability | Often implicit in scripts | Explicit thresholds in `security enforce` output |
| CI review speed | Depends on who wrote scripts | Consistent artifact structure across runs |
| Release handoff | Human summary in chat | Attach `build/*.json` as decision evidence |

## Minimal review playbook

1. Open `build/release-preflight.json`.
2. If it references `gate_fast`, open `build/gate-fast.json`.
3. If policy is failing, open `build/security-enforce.json` and inspect `exceeded`.
4. Only then deep-dive into raw logs.

## How to reference artifacts in PRs or release discussions

Use artifact fields directly instead of long raw log excerpts:

- Link to uploaded `build/release-preflight.json`.
- Include `ok` and `failed_steps` values in the PR summary.
- If security policy is relevant, include `counts`/`exceeded` from `build/security-enforce.json`.

This keeps decisions auditable without inventing claims or hiding failing context.

## Where to go next

- Canonical release-confidence model: [Release confidence](release-confidence.md)
- Artifact decode rules: [CI artifact walkthrough](ci-artifact-walkthrough.md)
- Fit check: [Decision guide](decision-guide.md)
