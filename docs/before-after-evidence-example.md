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

Representative real shapes are documented in [Evidence showcase](evidence-showcase.md).

## What this changes in practice

| Decision step | Before (log-only) | After (SDETKit evidence) |
| --- | --- | --- |
| First triage move | Read mixed console output | Open JSON artifact and check `ok` + `failed_steps` |
| Policy traceability | Often implicit in scripts | Explicit thresholds in `security enforce` (`counts`, `exceeded`) |
| CI review speed | Depends on who wrote scripts | Consistent artifact structure across runs |
| Release handoff | Human summary in chat | Attach artifact links + machine-readable fields |

## Minimal review playbook

1. Open `build/release-preflight.json`.
2. If it references `gate_fast`, open `build/gate-fast.json`.
3. If policy is relevant, open `build/security-enforce.json` and inspect `counts` + `exceeded`.
4. Only then deep-dive into raw logs.

## Canonical PR comment template (copy/paste)

```md
### Release-confidence evidence
- Artifact: `build/release-preflight.json`
  - `ok`: <value>
  - `failed_steps`: <value>
- Artifact: `build/gate-fast.json`
  - `ok`: <value>
  - `failed_steps`: <value>
- Artifact: `build/security-enforce.json` (if used in this run)
  - `ok`: <value>
  - `counts`: <value>
  - `exceeded`: <value>

Decision: <go / no-go / conditional> based on the fields above.
```

## Canonical release discussion template (copy/paste)

```md
## Release evidence summary
- `build/release-preflight.json` -> `ok`: <value>, `failed_steps`: <value>
- `build/gate-fast.json` -> `ok`: <value>, `failed_steps`: <value>
- `build/security-enforce.json` -> `ok`: <value>, `counts`: <value>, `exceeded`: <value>

Release recommendation: <ready / not ready / ready with follow-up>.
```

## Where to go next

- Canonical release-confidence model: [Release confidence](release-confidence.md)
- Canonical artifact decode: [CI artifact walkthrough](ci-artifact-walkthrough.md)
- Fit check: [Decision guide](decision-guide.md)
