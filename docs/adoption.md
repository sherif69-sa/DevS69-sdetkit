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
```

## Review real-world adoption learning

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
