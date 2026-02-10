```markdown
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

See: doctor.md

## patch_harness

Deterministic, spec-driven file edits.

Examples:

- `python tools/patch_harness.py spec.json --check`
- `python tools/patch_harness.py spec.json --dry-run`
- `python tools/patch_harness.py spec.json`

See: patch-harness.md
````
