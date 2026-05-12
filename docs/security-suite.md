# Security suite

The `security` pack adds deterministic, offline repository security checks designed for CI and local auditing.

## Enable

```bash
sdetkit repo audit . --pack security --format json
sdetkit repo fix-audit . --pack security --dry-run
```

Use this pack alongside existing packs as needed, for example `--pack core,security`.

## Rules

### Secrets hygiene

- `SEC_SECRETS_ENV_IN_REPO`
  - Detects committed `.env`, `.env.*` (except `.env.example`), `.envrc`, `*.pem`, `*.key`, `id_rsa`, `id_dsa`.
  - Severity is `warn` for env-like files and `error` for key-like files outside fixture allowlist paths.
- `SEC_SECRETS_TEST_FIXTURES_ALLOW`
  - Allows test fixture paths (`tests/fixtures/**`, `test/fixtures/**`) while still warning for key-like filenames.

### GitHub security baseline

- `SEC_GH_CODEOWNERS_MISSING` (`warn`)
  - Checks `CODEOWNERS`, `.github/CODEOWNERS`, `docs/CODEOWNERS`.
- `SEC_GH_SECURITY_MD_MISSING` (`warn`)
  - Checks for `SECURITY.md`.
- `SEC_GH_DEPENDABOT_MISSING` (`warn`)
  - Checks for `.github/dependabot.yml`.
- `SEC_GH_ACTIONS_PINNING` (`warn`)
  - Line-based workflow scanner detects floating `uses:` refs such as `@main` / `@master`.
- `SEC_GH_PERMISSIONS_MISSING` (`warn`)
  - Warns when workflow files do not define a `permissions:` block.

### Python security hygiene

- `SEC_PY_DEPENDENCY_FILES_MISSING` (`warn`)
  - If a repo looks Python-based, requires at least one dependency declaration (`pyproject.toml` or `requirements*.txt`).
- `SEC_PY_PRECOMMIT_MISSING` (`warn`, fixable)
  - Recommends `.pre-commit-config.yaml`.
- `SEC_PY_BANDIT_CONFIG_HINT` (`info`)
  - Informational hint when no Bandit config is present.

## Autofixable security items

`fix-audit` supports safe template generation for missing files:

- `SEC_GH_SECURITY_MD_MISSING` → `SECURITY.md`
- `SEC_GH_CODEOWNERS_MISSING` → `.github/CODEOWNERS`
- `SEC_GH_DEPENDABOT_MISSING` → `.github/dependabot.yml`
- `SEC_PY_PRECOMMIT_MISSING` → `.pre-commit-config.yaml`

Safety model:

- Never overwrites existing files unless `--force` is supplied.
- Generates deterministic content with stable ordering and LF newlines.
- Uses generic templates without repo-specific owner hardcoding.

## Tuning false positives

Use policy/config controls:

- `exclude_paths` for path-level suppression.
- `allowlist` for governed suppressions with rule/path/message constraints.

Example:

```toml
[tool.sdetkit.repo_audit]
exclude_paths = ["tests/fixtures/**"]
allowlist = [
  { rule_id = "SEC_SECRETS_TEST_FIXTURES_ALLOW", path = "tests/fixtures/id_rsa" }
]
```

## Info-level findings

By default, `sdetkit security check` excludes info-level findings from `new_findings` and summaries.
Use `--include-info` to include them (for example, to surface `SEC_DEBUG_PRINT` notes).
