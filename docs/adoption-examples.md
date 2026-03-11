# Adoption examples: practical first rollout shapes

These examples are intentionally small and realistic.

They use the existing Stable/Core command path for **release confidence / shipping readiness** and avoid unsupported integrations or "big bang" rollouts.

## 1) Solo maintainer with a small Python repository

**Who this is for**

- One maintainer (or very small team) running a Python package/service repo.
- You want a quick, repeatable ship/no-ship signal without heavy CI redesign.

**Starting goal**

- Get a deterministic baseline signal locally, then mirror it in CI.

**Recommended first commands**

```bash
python -m sdetkit gate fast
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
```

**Add next after initial success**

- Add a minimal CI job that runs `python -m sdetkit gate fast` on pull requests.
- Use [adoption-troubleshooting.md](adoption-troubleshooting.md) and [remediation-cookbook.md](remediation-cookbook.md) if the first failures expose cleanup work.

**What not to do yet (common overreach)**

- Do not start with strict zero-budget security enforcement if the repo has known debt.
- Do not add multiple new gates at once before `gate fast` is consistently green.

## 2) Team tightening release checks in an existing service repo

**Who this is for**

- A team with an existing CI pipeline that already runs tests/lint, but no clear release gate.

**Starting goal**

- Keep PR feedback fast, and add a stricter release branch path for higher shipping confidence.

**Recommended first commands**

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0 --out build/security-enforce.json
python -m sdetkit gate release --format json --out build/release-preflight.json
```

Use the staged rollout from [adoption.md](adoption.md) and the branch strategy in [recommended-ci-flow.md](recommended-ci-flow.md).

**Add next after initial success**

- Upload `build/*.json` as CI artifacts so reviewers can triage failures from structured output.
- Move strict checks to release branches first, then expand scope once flakiness and debt are reduced.

**What not to do yet (common overreach)**

- Do not block every branch on the strictest path on day one.
- Do not treat first strict failures as tool issues; route them as release-readiness backlog.

## 3) Repo starting with core path first, then expanding into integrations/playbooks

**Who this is for**

- Teams new to SDETKit that want to avoid premature adoption of advanced lanes.

**Starting goal**

- Prove value quickly with the flagship core path, then layer integrations/playbooks intentionally.

**Recommended first commands**

In this repository:

```bash
bash scripts/ready_to_use.sh quick
bash scripts/ready_to_use.sh release
```

In an external repository:

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
```

**Add next after initial success**

- Add CI automation using [github-action.md](github-action.md) or [adoption.md](adoption.md).
- Add guided operational rollout with a focused playbook only after core gates are routine (see [examples.md](examples.md)).

**What not to do yet (common overreach)**

- Do not start from historical or specialized integration pages before core commands are understood.
- Do not expand into multiple playbooks simultaneously without a stable core gate baseline.

## Quick decision aid

- Need fastest first proof in a single repo: start with Scenario 1.
- Need branch-aware release tightening in team CI: start with Scenario 2.
- Need phased adoption from core into broader SDETKit usage: start with Scenario 3.

## Related docs

- [Ready-to-use setup](ready-to-use.md)
- [Adopt SDETKit in your repository](adoption.md)
- [Example adoption flow](example-adoption-flow.md)
- [Recommended CI flow](recommended-ci-flow.md)
