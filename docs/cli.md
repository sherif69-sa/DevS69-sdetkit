# CLI

## kv

Reads key=value lines (stdin, --text, or --path) and prints JSON.

Examples:

- `sdetkit kv --text "a=1\nb=two"`
- `echo -e "a=1\nb=two" | sdetkit kv`
- `kvcli --help`

## apiget

Fetch JSON from a URL with retries, pagination, and trace helpers.

Examples:

- `sdetkit apiget https://example.com/api --expect dict`
- `sdetkit apiget https://example.com/items --expect list --paginate --max-pages 50`
- `sdetkit apiget https://example.com/items --expect list --retries 3 --retry-429 --timeout 2`
- `sdetkit apiget https://example.com/items --expect any --trace-header X-Request-ID --request-id abc-123`

## doctor

Repo health checks and diagnostics.

Examples:

- `sdetkit doctor --ascii`
- `sdetkit doctor --all`
- `sdetkit doctor --all --json`
- `sdetkit doctor --dev --ci --deps --clean-tree --pr`

See: doctor.md

## patch

Deterministic, spec-driven file edits (official CLI command).

Examples:

- `sdetkit patch spec.json --check`
- `sdetkit patch spec.json --dry-run`
- `sdetkit patch spec.json --root /workspace/myrepo`
- `sdetkit patch spec.json --report-json patch-report.json`

`--root` defaults to the current Git repository root (when inside a repo) and falls back to the current working directory otherwise.

Exit codes: `0` success/no-op, `1` changes required in `--check`, `2` invalid/unsafe/error.

Safety limits include `--max-files`, `--max-bytes-per-file`, `--max-total-bytes-changed`, `--max-op-count`, and `--max-spec-bytes`.

Backward compatibility wrapper still works:

- `python tools/patch_harness.py spec.json --check`

See: patch-harness.md


## Security defaults

All CLI tools now default to safer behavior:

- Secret redaction is ON by default for printed HTTP request/response metadata (`--redact`, `--no-redact`, `--redact-keys KEY`).
- HTTP clients enforce explicit timeouts and allow only `http/https` schemes by default (`--allow-scheme`).
- Redirect behavior is explicit (`--follow-redirects` / `--no-follow-redirects`).
- TLS verification stays enabled by default; `--insecure` is opt-in and emits a warning.
- File outputs refuse unsafe paths and existing files unless explicitly forced (`--force`).

Tool-specific notes:

- `apiget`: supports redaction flags, scheme allowlist, secure timeout defaults, explicit redirects, and safe output writes.
- `cassette-get`: supports scheme allowlist, secure timeout defaults, explicit redirects, safe cassette writes, and `--force` for overwrites.
- `kv`: input parsing remains backward compatible for stdin, --text, and --path usage.
- `patch`: report output uses safe paths + atomic writes and requires `--force` to overwrite.
- `doctor`: returns `1` for failing checks, `0` for pass, while usage/runtime issues map to `2` in shared CLI wrappers.


## `repo`

- `sdetkit repo audit [PATH] [--profile default|enterprise] [--format text|json|sarif] [--output PATH] [--fail-on none|warn|error] [--force]`
- `sdetkit repo check [PATH] [--format text|json|md] [--out PATH] [--fail-on LEVEL] [--min-score N]`
- `sdetkit repo fix [PATH] [--check|--dry-run] [--diff] [--eol lf|crlf]`
- `sdetkit repo init [PATH] [--profile default|enterprise] [--dry-run] [--apply] [--force] [--diff]`
- Security-first defaults: safe paths, deterministic sorted outputs, and atomic writes.

Audit examples:

- `sdetkit repo audit`
- `sdetkit repo audit --format json --out repo-audit.json --force`

Init examples:

- `sdetkit repo init` (safe dry-run default)
- `sdetkit repo init --diff`
- `sdetkit repo init --apply --profile enterprise`

See: repo-init.md

GitHub Action integration:

- Use `.github/actions/repo-audit` for CI summary + SARIF + JSON artifact workflows.
- See: github-action.md
