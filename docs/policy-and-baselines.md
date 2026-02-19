# Policy and baselines (`sdetkit repo audit`)

Phase 4 adds company-grade policy and baseline controls to keep `repo audit` signal high while staying deterministic and offline.

## Configuration location

`sdetkit` reads policy from `pyproject.toml` at:

```toml
[tool.sdetkit.repo_audit]
profile = "enterprise"
fail_on = "warn"
baseline_path = ".sdetkit/audit-baseline.json"
exclude_paths = ["docs/**", ".venv/**", "dist/**"]
disable_rules = ["repo_audit/missing_repo_hygiene_item"]
severity_overrides = { "repo_audit/large_tracked_file" = "error" }
allowlist = [
  { rule_id = "repo_audit/missing_repo_hygiene_item", path = "examples/**" },
  { rule_id = "repo_audit/missing_ci_policy", path = "legacy/**", contains = "accepted for legacy" }
]
```

## Precedence (deterministic)

1. CLI flags
2. `pyproject.toml` policy
3. profile defaults

No network calls are used for policy/baseline resolution.

## Baseline workflow

Create baseline:

```bash
sdetkit repo baseline create .
```

Check drift (NEW/RESOLVED/UNCHANGED):

```bash
sdetkit repo baseline check . --diff
```

Update baseline in-place:

```bash
sdetkit repo baseline check . --update --fail-on none
```

Baseline JSON format:

- `schema_version`
- optional metadata (`created_at`, `tool_version`)
- `entries`: `rule_id`, `path`, `fingerprint`, `severity`, `message_key`

Fingerprints are deterministic hashes of rule id + normalized path + stable message key.

## `repo audit` integration

`repo audit` supports:

- `--config PATH`
- `--baseline PATH`
- `--update-baseline`
- `--exclude GLOB` (repeatable)
- `--disable-rule RULE_ID` (repeatable)

When baseline is present and `--update-baseline` is not used, baseline-matching findings are suppressed from actionable output and fail gating.

Text output includes:

- total findings
- suppressed by baseline
- suppressed by policy (`exclude_paths`, `disable_rules`, `allowlist`)
- actionable findings

JSON output includes suppression records and aggregate suppression counters.
SARIF output includes actionable findings only.

## CI + GitHub Action guidance

Use baseline-aware `repo audit` in CI for stable gates while keeping trend visibility through baseline check output and optional JSON artifacts/step summary from the Phase 3 GitHub Action workflow.
