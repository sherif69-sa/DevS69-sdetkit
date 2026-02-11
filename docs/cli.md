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
