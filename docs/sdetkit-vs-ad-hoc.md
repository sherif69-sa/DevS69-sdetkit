# SDETKit vs ad hoc scripts and separate tools

**Use this page if:** you need the canonical comparison page for “why SDETKit vs ad hoc scripting”.

Running separate tools is still valid. This comparison explains why teams adopt SDETKit when they need repeatable release decisions, not just command execution.

## Short answer

Ad hoc scripts optimize for local flexibility.
SDETKit optimizes for deterministic gate semantics, structured evidence, and consistent rollout from local runs to CI.

## Comparison grounded in current command surface

| Dimension | Ad hoc scripts + separate tools | SDETKit path |
| --- | --- | --- |
| Command contract | Varies by repo/maintainer | Stable gate commands (`gate fast`, `gate release`, `doctor`, `security enforce`) |
| Decision output | Mostly terminal logs | JSON artifacts (`build/gate-fast.json`, `build/security-enforce.json`, `build/release-preflight.json`) |
| CI portability | Requires custom per-repo glue | Same core commands locally and in CI |
| Triage behavior | Human interpretation of logs | Deterministic keys (`ok`, `failed_steps`, `counts`, `exceeded`) |
| Adoption model | Tribal scripts and runbooks | Documented staged rollout (`adoption.md`, `recommended-ci-flow.md`) |

## Where SDETKit adds value

- **Consistency:** shared go/no-go semantics across contributors.
- **Reproducibility:** same commands for local and CI checks.
- **Evidence:** machine-readable artifacts suitable for review and audits.
- **Governance:** explicit budget and gate thresholds.

## Where ad hoc can still be enough

- Very small repos with low release risk.
- Single maintainer workflows where formal evidence is unnecessary.
- Teams intentionally avoiding a standardized gate model.

## Recommended evaluation recipe

Run this in your repo and inspect artifacts before deciding:

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0 --out build/security-enforce.json
python -m sdetkit gate release --format json --stable-json --out build/release-preflight.json
```

If this gives your team faster and clearer release decisions, adopt progressively; if not, keep your lighter ad hoc path.

## Where to go next

- Ready to try it: [First run quickstart](ready-to-use.md).
- Ready for rollout: [Adoption](adoption.md) and [Recommended CI flow](recommended-ci-flow.md).
- For the longer system-value argument: [Why not just run separate tools?](why-not-just-tools.md).
