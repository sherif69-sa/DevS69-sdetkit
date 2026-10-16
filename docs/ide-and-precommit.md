# IDE + pre-commit integration

## Run the gate as a pre-commit hook

This repository publishes a [pre-commit](https://pre-commit.com) hook, `sdetkit-gate`, that runs `sdetkit gate fast` before each push. Add it to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/sherif69-sa/DevS69-sdetkit
    rev: v2.0.0
    hooks:
      - id: sdetkit-gate
```

Then install the pre-push hook:

```bash
pre-commit install --hook-type pre-push
```

What it does:

- It runs `gate fast` once on the whole repository, whatever files changed: the same steps, verdict and next command as on the command line.
- The push stops when the gate exits non-zero: a check failed (`NO_SHIP`), or a check could not run (`NOT_RUN` with `classification: environment`, for example when the project is not installed where the tests ran). The output names the failing step, the first failure and the command to run next.
- It runs at `pre-push` because the gate runs your tests. To run it on every commit instead, add `stages: [pre-commit]` under the hook; to run it on demand, use `pre-commit run sdetkit-gate --hook-stage manual --all-files`.
- Options go in `args`, for example `args: [--only, "ruff,mypy"]` for a quicker check, or `args: [--skip, pytest]`.

Which interpreter runs your checks: pre-commit installs SDETKit in an environment of its own, so the gate looks for yours. It uses the repository's `.venv` or `venv`, Poetry's or Pipenv's environment, and otherwise the first `python` on `PATH` outside pre-commit's environment, which is your activated virtualenv when you have one. When that interpreter does not have the project installed, or has no pytest, the gate reports `NOT_RUN` with the command that sets the environment up, not a test failure. When your environment has no ruff or mypy, add them to the hook with `additional_dependencies: [ruff, mypy]`. See [which Python runs your checks](cli.md#which-python-runs-your-checks).

CI's `Pre-commit hook (self)` job runs this hook with `pre-commit try-repo` on every change to this repository: on a project whose tests pass, one whose test fails, and one with no environment.

## Write a local hook with `dev precommit install`

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
