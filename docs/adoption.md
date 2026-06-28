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
python -m pip install sdetkit==1.0.3
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

Maintainers can aggregate read-only observations from a verified matrix of external repository roots, then convert the resulting matrix artifact into a review-first learning report.

First, generate the real-world learning matrix from repository roots whose licenses and local paths have already been verified:

```bash
python -m sdetkit adoption-real-world-learning-matrix \
  --matrix-json <verified-repo-matrix.json> \
  --artifact-root build/sdetkit/adoption-real-world-learning \
  --out build/sdetkit/adoption-real-world-learning/adoption-real-world-matrix.json \
  --markdown-out build/sdetkit/adoption-real-world-learning/adoption-real-world-matrix.md \
  --minimum-repos 10 \
  --format json
```

The matrix lane inspects repository surfaces without installing dependencies, running target tests, changing target repositories, or opening target issues or pull requests. A fully passed matrix returns exit code `0`; a matrix that requires human review returns exit code `2` while still writing its evidence artifacts.

Then generate the prioritized adoption learning report:

```bash
python -m sdetkit adoption-learning-report \
  --matrix-json build/sdetkit/adoption-real-world-learning/adoption-real-world-matrix.json \
  --out build/sdetkit/adoption-learning-report.json \
  --markdown-out build/sdetkit/adoption-learning-report.md \
  --format json
```

The report command reads the matrix artifact and, when explicitly provided, an optional RepoMemory profile. It does not revisit the target repositories, execute proof commands, apply patches, or make a current-PR decision.

Read these JSON fields first:

- `source_matrix_schema_version`
- `source_matrix_status`
- `source_repo_count`
- `candidate_count`
- `top_candidate`
- `prioritized_upgrade_candidates`
- `repo_memory_profile`
- `operator_summary`
- `rules`
- `authority_boundary`

Each candidate remains review-first. `safe_to_patch=false` means the report is evidence for a human-scoped follow-up, not approval to edit another repository.

The report preserves these boundaries:

```text
automation_allowed=false
patch_application_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
```

The generated JSON artifact is registered as `adoption-learning-report-json` at `build/sdetkit/adoption-learning-report.json`. The Markdown file is an operator-readable companion, not a separate machine schema.

## Render the recorded public trial matrix

Use the dedicated reporting-only lane when the input is the recorded
`sdetkit.public_repo_trial_matrix.v1` fixture contract rather than a live
real-world learning matrix:

```bash
python -m sdetkit adoption-public-trial-matrix-report \
  --matrix-json tests/fixtures/adoption_public_trials/public_repo_trial_matrix.json \
  --out build/sdetkit/public-repo-trial-matrix-report.json \
  --markdown-out build/sdetkit/public-repo-trial-matrix-report.md \
  --format json
```

The command reads only the supplied matrix artifact. It does not revisit the
listed repositories, install dependencies, execute target tests, mutate a
target, open a target issue or pull request, claim endorsement, or authorize
an implementation.

Read these JSON fields first:

- `report_status`
- `input_provenance`
- `source_matrix`
- `summary`
- `trials`
- `operator_summary`
- `rules`
- `authority_boundary`

The report binds the source matrix bytes and current Git head into a SHA-256
input digest. Its trial list is sorted by repository name so JSON and Markdown
remain deterministic for the same matrix and head.

The authority boundary remains:

```text
target_repos_read=false
install_dependencies=false
target_tests_executed=false
target_repo_mutation=false
target_pr_or_issue_opened=false
endorsement_claim=false
automation_allowed=false
patch_application_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
```

The generated JSON artifact is registered as
`public-repo-trial-matrix-report-json` at
`build/sdetkit/public-repo-trial-matrix-report.json`. The Markdown file remains
an operator-readable companion rather than a separate machine contract.

## Render the adoption learning dashboard

After generating `build/sdetkit/adoption-learning-report.json`, render a static local dashboard for human review:

```bash
sdetkit-adoption-learning-report-dashboard \
  --report-path build/sdetkit/adoption-learning-report.json \
  --format html \
  --out build/sdetkit/adoption-learning-report-dashboard.html
```

The equivalent Python module command remains available:

```bash
python -m sdetkit.adoption_learning_report_dashboard \
  --report-path build/sdetkit/adoption-learning-report.json \
  --format html \
  --out build/sdetkit/adoption-learning-report-dashboard.html
```

For deterministic machine-readable output, select JSON explicitly:

```bash
sdetkit-adoption-learning-report-dashboard \
  --report-path build/sdetkit/adoption-learning-report.json \
  --format json \
  --out build/sdetkit/adoption-learning-report-dashboard.json
```

The dashboard validates the accepted source schema `sdetkit.adoption_learning_report.v1` and checks that `candidate_count` matches `prioritized_upgrade_candidates`. A successful render returns exit code `0`. Missing, malformed, unsupported-schema, or inconsistent input returns exit code `2` without creating the requested dashboard output.

Read these dashboard JSON fields first:

- `schema_version`
- `status`
- `source_report_schema_version`
- `source_matrix_schema_version`
- `source_matrix_status`
- `source_repo_count`
- `candidate_count`
- `top_candidate`
- `prioritized_upgrade_candidates`
- `repo_memory_profile`
- `operator_summary`
- `local_only`
- `read_only`
- `decision_boundary`

The HTML output is static and escapes report-provided text. It contains no JavaScript, performs no network access, and does not mutate the source adoption learning report. The JSON output is a deterministic read-only projection of the same accepted Python source of truth.

The dashboard preserves these non-authorizing boundaries:

```text
current_pr_decision_input=false
automation_allowed=false
proof_commands_executed=false
patch_application_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
```

The default HTML output path is `build/sdetkit/adoption-learning-report-dashboard.html`. The optional JSON dashboard is not yet a separately registered artifact contract; artifact-index registration remains a distinct follow-up.
