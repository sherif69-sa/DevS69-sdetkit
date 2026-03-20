# Automation templates engine

The AgentOS automation templates engine lets teams run repeatable workflows locally without paid LLM services.

## Why it matters for enterprise teams

- Standardized automation playbooks as YAML templates.
- Deterministic execution and packaging for auditability.
- Easy distribution of approved template bundles across teams.
- Reusable building blocks based on AgentOS actions (`repo.audit`, `report.build`, `fs.write`, `shell.run`).

## Template schema

Templates live in `templates/automations/*.yaml` and must contain:

- `metadata`: `id`, `title`, `version`, `description`
- `inputs`: named parameters with defaults (and optional descriptions)
- `workflow`: ordered steps with:
  - `id` (optional)
  - `action`
  - `with` parameter map

Interpolation is safe and explicit: `${{inputs.foo}}`, `${{run.output_dir}}`, `${{template.id}}`.

## CLI

- `sdetkit agent templates list`
- `sdetkit agent templates show <id>`
- `sdetkit agent templates run <id> [--set key=value ...] [--output-dir DIR]`
- `sdetkit agent templates pack [--output FILE.tar]`

## Add new templates

1. Add a YAML file under `templates/automations/`.
2. Fill metadata, inputs, and workflow.
3. Use supported actions and deterministic file outputs.
4. Run tests to validate parsing and execution behavior.

## Distribution packs

Use `sdetkit agent templates pack` to create a deterministic tar archive of templates. This enables:

- internal artifact registry publishing
- signed release bundles
- reproducible template rollouts in CI/CD

## Included templates

- `repo-health-audit`
- `security-governance-summary`
- `change-only-audit`
- `report-dashboard`
- `baseline-update-gated`
- `precommit-style-checks`
- `dependency-outdated-report`
- `ci-artifact-bundle`
- `dependency-radar-worker`
- `validation-route-worker`
- `worker-alignment-radar`
- `docs-search-radar`
- `release-readiness-worker`
- `repo-expansion-control`
