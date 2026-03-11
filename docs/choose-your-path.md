# Choose your path: compact adoption and rollout guide

Use this page to pick the safest rollout path after the core story is clear: **deterministic release-confidence checks and evidence-backed shipping decisions**.

## Core command set (same in all paths)

- `python -m sdetkit gate fast`
- `python -m sdetkit gate release`
- `python -m sdetkit doctor`
- `python -m sdetkit evidence --help`
- `python -m sdetkit report --help`

## If this sounds like you, start here

| Repo situation | Choose this path | First command(s) | Add next | Postpone for now |
| --- | --- | --- | --- | --- |
| Small or clean repo, want fast signal in minutes | **Path A — Fast signal first** | `python -m sdetkit gate fast` | Add CI `gate fast` and collect JSON evidence (`--format json --stable-json --out build/gate-fast.json`). | Strict enforcement on every branch. |
| Existing repo has CI, but quality/security discipline is uneven | **Path B — Stabilize baseline, then tighten** | `python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json` | Add `python -m sdetkit gate release`, keep evidence artifacts in CI, and use `doctor` in triage loops. | Broad integration/playbook expansion before core gates are stable. |
| Team needs strict release approvals now | **Path C — Release confidence first** | `python -m sdetkit gate release` | Keep `gate fast` on PRs, run `doctor` before release windows, and standardize evidence/report review in release sign-off. | Non-core taxonomy exploration during initial rollout. |

## Minimal rollout order (safe default)

1. Start with **Path A** for first signal.
2. Move to **Path B** when recurring failures and uneven discipline appear.
3. Apply **Path C** when release approvals need strict, auditable confidence.

## Next reading

- [Decision guide (fit assessment)](decision-guide.md)
- [Ready-to-use setup](ready-to-use.md)
- [Adopt SDETKit in your repository](adoption.md)
- [Recommended CI flow](recommended-ci-flow.md)
- [Evidence showcase](evidence-showcase.md)
