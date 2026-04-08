# Choose your path (30-second router)

Use this page to pick one outcome-focused path quickly.

Core promise: deterministic release-confidence checks and evidence-backed shipping decisions.

| Who this is for | First page to open | First command or proof step | Expected outcome |
| --- | --- | --- | --- |
| Evaluating fit in a new repo | [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md) | `python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json` | You get immediate machine-readable go/no-go evidence. |
| New user wanting guided onboarding | [First run quickstart](ready-to-use.md) | `python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json` then `python -m sdetkit gate release --format json --out build/release-preflight.json` | You complete the canonical local command path with clear artifacts. |
| Team rolling out policy in CI | [Recommended CI flow](recommended-ci-flow.md) | Upload `build/*.json` artifacts from gate runs | Release checks become repeatable and reviewable in CI. |
| Stakeholder asking “why this vs ad hoc?” | [Before/after evidence example](before-after-evidence-example.md) | Compare log-only triage vs JSON artifact triage | Decision quality and traceability become explicit. |

## Default sequence (recommended)

1. Install
2. 60-second proof
3. Guided first run
4. Team/CI rollout

Use advanced/reference material only after this core sequence is stable.
