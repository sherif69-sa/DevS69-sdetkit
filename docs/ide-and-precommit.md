# IDE + pre-commit integration

## Install pre-commit hook

Use the developer helper to plan first, then apply:

- Dry-run plan: `sdetkit dev precommit install . --dry-run --diff`
- Write file: `sdetkit dev precommit install . --apply`

Default hook command is optimized for local speed:

- `sdetkit repo audit --pack core --changed-only --fail-on error`

You can customize profile/pack/mode:

- `sdetkit dev precommit install . --profile enterprise --pack core,security --mode full --apply`

## Recommended hook modes

- `changed-only` (default): fast feedback on staged/changed files.
- `full`: slower but catches full-repo issues before commit.

In monorepos, keep pre-commit on `changed-only` and run a full scheduled/CI audit.

## IDE diagnostics output

`repo audit` can write deterministic IDE JSON diagnostics:

- `sdetkit repo audit --ide generic --ide-output .sdetkit/diag.json`
- `sdetkit repo audit --ide vscode --ide-output .sdetkit/diag.json`

Output schema:

```json
{
  "schema_version": "sdetkit.ide.diagnostics.v1",
  "diagnostics": [
    {
      "path": "src/pkg/file.py",
      "line": 12,
      "col": 4,
      "severity": "error",
      "code": "missing_repo_hygiene_item",
      "message": "required repository hygiene item is missing: LICENSE",
      "fixable": false
    }
  ]
}
```

By default, suppressed findings are not emitted. Use `--include-suppressed` to inspect everything in IDE tooling.

SARIF remains available for compatible IDEs:

- `sdetkit repo audit --format sarif --output .sdetkit/repo-audit.sarif --force`

## VS Code task example

```json
{
  "label": "sdetkit: audit changed",
  "type": "shell",
  "command": "sdetkit repo audit --pack core --changed-only --ide vscode --ide-output .sdetkit/diag.json"
}
```

## Monorepo tips

- For project-level audits, pair `--all-projects` with `--ide-output` for aggregated diagnostics.
- Keep baseline and policy files per project where practical.
- Use `sdetkit dev audit` for day-to-day local checks and `sdetkit dev fix` for quick fix previews.
