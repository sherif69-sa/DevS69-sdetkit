# Plugins, rule packs, and `fix-audit`

Phase 5 turns `sdetkit repo audit` into a plugin-driven platform.

## Plugin API

Create a package exposing entry points:

- `sdetkit.repo_audit_rules`
- `sdetkit.repo_audit_fixers`

Rule plugin contract (from `sdetkit.plugins`):

- `RuleMeta`: stable `id`, title/description, default severity, tags, fix support.
- `Finding`: includes `rule_id`, message, optional path/line/details, stable fingerprint.
- `AuditRule.run(repo_root, context) -> list[Finding]`.
- Optional fixer: `Fixer.fix(repo_root, findings, context) -> list[Fix]`.

Minimal rule example:

```python
from pathlib import Path
from sdetkit.plugins import Finding, RuleMeta

class MyRule:
    meta = RuleMeta(
        id="ACME_README_MISSING",
        title="README present",
        description="README.md must exist",
        default_severity="warn",
        tags=("pack:core", "acme"),
        supports_fix=False,
    )

    def run(self, repo_root: Path, context: dict[str, object]) -> list[Finding]:
        if (repo_root / "README.md").exists():
            return []
        return [Finding(rule_id=self.meta.id, severity="warn", message="missing README.md", path="README.md").with_fingerprint()]
```

Register in `pyproject.toml`:

```toml
[project.entry-points."sdetkit.repo_audit_rules"]
acme_readme = "acme.audit:MyRule"
```

## Rule packs

Built-in packs:

- `core`
- `enterprise`
- `security`

Defaults:

- profile `default` => `core`
- profile `enterprise` => `core,enterprise`

Use packs explicitly:

```bash
sdetkit repo rules list --pack core,security --json
sdetkit repo audit . --pack core,enterprise --format json
```

## Auto-fix engine

`fix-audit` runs the same audit + policy/baseline suppression pipeline, then calls available fixers.

```bash
sdetkit repo fix-audit . --dry-run --diff --patch repo-audit.patch
sdetkit repo fix-audit . --apply
```

### Safety model

- Deterministic ordering for rules/findings/fixes/diffs.
- No patch file overwrite unless `--force`.
- Only fixes marked `safe=true` are applied unless `--force`.
- `--apply` writes through atomic writes.
- Idempotent by design: second apply should produce no changes.

Built-in safe fixers create only missing governance/config templates:

- `SECURITY.md`
- `CODE_OF_CONDUCT.md`
- `CONTRIBUTING.md`
- `.github/ISSUE_TEMPLATE/config.yml`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/dependabot.yml`
- `.github/workflows/repo-audit.yml`
