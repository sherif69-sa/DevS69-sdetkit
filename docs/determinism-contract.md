# Determinism contract

This project guarantees deterministic output structures for offline (`provider=none`) workflows.

## Guaranteed deterministic

- Canonical JSON serialization for run/history records (`ensure_ascii`, sorted keys).
- Stable list ordering for findings, top-N summaries, recurring rules/paths, and history indexes.
- Deterministic tar packaging for template bundles (sorted paths, fixed uid/gid/mtime).
- Atomic writes for generated artifacts to avoid partial outputs.
- HTML escaping for user-supplied text rendered in dashboards.

## Not guaranteed deterministic

- Wall-clock timestamps when `SOURCE_DATE_EPOCH` is not set.
- External command output from `shell.run` actions.
- Any provider-generated text when `provider.type=local` is used.

## Best-practice reproducible runs

1. Use `provider.type=none`.
2. Set `SOURCE_DATE_EPOCH` for stable timestamps.
3. Keep input files stable and run from a clean tree.
4. Use explicit output paths (`--output`, `--output-dir`, `--history-dir`).
