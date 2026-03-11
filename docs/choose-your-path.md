# Choose your path: compact adoption and rollout guide

Use this page to quickly pick the safest first rollout path for your repository.

The default product direction stays the same: **release confidence / shipping readiness for software teams**.

## If this sounds like you, start here

| Repo situation | Choose this path | First command(s) | Add next | Postpone for now |
| --- | --- | --- | --- | --- |
| Small or clean repo, want fast signal in minutes | **Path A — Fast signal first** | `python -m sdetkit gate fast` | Add CI `gate fast` on PRs and pushes; keep JSON output for triage (`--format json --stable-json --out build/gate-fast.json`). | Strict zero-budget enforcement and release gating on every branch. |
| Existing repo already has CI, but quality/security discipline is uneven | **Path B — Stabilize baseline, then tighten** | `python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json` | Fix top recurring failures, upload `build/*.json` artifacts, then add `python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0` on release branches first. | Blocking all branches immediately with strict security + release checks. |
| Team wants stricter release confidence before broader expansion | **Path C — Release confidence first** | `python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0` then `python -m sdetkit gate release` | Keep `gate fast` on PRs, keep strict checks on release branches/tags, and standardize artifact review in release decisions. | Expanding into broader integrations/playbooks before strict release path is routine. |

## Minimal rollout order (safe default)

1. Start with **Path A** for first signal.
2. Move to **Path B** when recurring failures and uneven discipline appear.
3. Apply **Path C** when release decisions need stricter, auditable confidence.

## Command set used in all paths

These are the same existing, supported commands already used in adoption docs:

- `python -m sdetkit gate fast`
- `python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0`
- `python -m sdetkit gate release`

## Next reading

- [Adopt SDETKit in your repository](adoption.md)
- [Adoption examples](adoption-examples.md)
- [Ready-to-use setup](ready-to-use.md)
- [Recommended CI flow](recommended-ci-flow.md)
- [Decision guide (fit assessment)](decision-guide.md)
