- Compact week-1 team plan: [Team rollout playbook](team-rollout-playbook.md)

# Adopt SDETKit in your repository (canonical)

**Use this page if:** you are introducing SDETKit to a team-owned repository and need a staged rollout plan.

**Not this page:**
- First solo run: [First run quickstart](ready-to-use.md)
- CI workflow templates and branch policies: [Recommended CI flow (canonical)](recommended-ci-flow.md)
- Artifact interpretation details: [CI artifact walkthrough (canonical)](ci-artifact-walkthrough.md)

## Adoption objective

Move from local confidence checks to repeatable team gates with machine-readable release evidence.

## Stage 0 — install and verify in target repo

Use [Install](install.md), then verify:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install sdetkit==1.2.0
python -m sdetkit --help
python -m sdetkit gate --help
```

For maintainers validating the external-install contract itself (from this repository):

```bash
python -m pytest -q tests/test_external_first_run_contract.py
```


## Optional preflight — capture the adoption surface

Before choosing rollout depth, capture a read-only repository surface artifact:

```bash
python -m sdetkit adoption-surface --root . --out build/sdetkit/adoption-surface.json --format text
```

Use the generated `build/sdetkit/adoption-surface.json` to review detected languages, package managers, CI systems, security tooling, artifact surfaces, and recommended proof commands.

This is an evidence-only handoff. It does not run proof commands, install dependencies, mutate the repository, authorize automation, or authorize merge.

## Build the diagnostic execution plan

Convert the discovered repository surface into a deterministic, non-executing command plan:

```bash
python -m sdetkit.diagnostic_execution_plan \
  --root . \
  --out build/sdetkit/diagnostic-execution-plan.json \
  --format json
```

The generated `diagnostic-execution-plan-json` artifact records ordered commands, structured
arguments, repository-relative working directories, evidence references, expected artifacts,
timeouts, review reasons, and isolation policies. It does not execute commands or authorize
execution, automation, dependency installation, target mutation, patch application, or merge.

## Stage 1 — local proof in the team repo

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
```

This is a signal-producing gate, not a guaranteed-green onboarding command.

## Stage 2 — baseline release confidence

```bash
python -m sdetkit gate release --format json --out build/release-preflight.json
```

Add security budgets once the team has agreement on thresholds:

```bash
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0 --out build/security-enforce.json
```

## Stage 3 — CI rollout (handoff)

Use [Recommended CI flow](recommended-ci-flow.md) as the canonical CI rollout source. It defines:

- PR fast-gate baseline
- main/release stricter gates
- artifact upload conventions
- progressive tightening without all-at-once friction

## Team operating model

- PR lane: keep `gate fast` always on.
- main/release lane: enforce agreed security budgets and release gates.
- triage: use artifact-first flow via [CI artifact walkthrough](ci-artifact-walkthrough.md).

## If onboarding fails

Use these in order:

1. [First-failure triage](first-failure-triage.md)
2. [Adoption troubleshooting](adoption-troubleshooting.md)
3. [Remediation cookbook](remediation-cookbook.md)

## Related rollout pages

- [Team rollout scenario](team-rollout-scenario.md)
- [Example adoption flow](example-adoption-flow.md)
- [Real repo adoption proof](real-repo-adoption.md)
- [Adoption examples](adoption-examples.md)
- [Choose your path](choose-your-path.md)

## Operator readiness report

Use the adoption-surface report when you want a human-readable, review-first summary before running commands in an adopted repository:

```bash
python -m sdetkit adoption-surface \
  --root . \
  --out build/sdetkit/adoption-surface.json \
  --format report
```

The report summarizes repository identity, detected languages, package managers, test runners, CI systems, security tools, recommended proof commands, review-first unknowns, and the authority boundary.

The command is intentionally read-only. Recommended proof commands are listed for the operator to review and run manually; they are not auto-run by SDETKit.

Authority boundary:

```text
automation_allowed=false
patch_application_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
automatic_security_fix_allowed=false
automatic_dismissal_allowed=false
```

## Adoption follow-up authority boundary

The public `adoption` command builds prioritized follow-up recommendations from fit and gate
decision artifacts:

```bash
python -m sdetkit adoption   --fit build/sdetkit-fit-recommendation.json   --summary build/gate-decision-summary.json   --format json   --out build/adoption-followup.json
```

Its recommendations are advisory and review-first. JSON, Markdown, history JSONL, and history
rollup outputs explicitly preserve:

```text
automation_allowed=false
patch_application_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
automatic_security_fix_allowed=false
automatic_dismissal_allowed=false
```

A recommendation or escalation signal does not authorize command execution, patch application,
security remediation, alert dismissal, branch creation, or merge. Those actions remain separate
human decisions.

## Review real-world adoption learning

These commands are intentionally hidden maintainer-only learning lanes. They are absent from
default root help by design so adopter-facing discovery remains focused:
- `adoption-real-world-learning-matrix`
- `adoption-learning-report`
- `adoption-public-trial-matrix-report`

Maintainers can reveal these commands with `python -m sdetkit --show-hidden --help`. Direct
command help remains available through `python -m sdetkit <command> --help`.

Hidden status is a discoverability contract, not action authority. Both commands remain
review-first and do not authorize proof execution, patch application, branch or pull-request
creation, security remediation, alert dismissal, or merge.
