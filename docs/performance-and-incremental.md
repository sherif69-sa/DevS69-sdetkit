# Performance and incremental mode

`sdetkit repo audit` supports optional performance features for large repositories while keeping deterministic output and offline behavior.

## Incremental changed-only mode

Use `--changed-only` to evaluate only rules affected by local Git changes.

```bash
sdetkit repo audit . --changed-only
```

Flags:

- `--since-ref REF` (default: `HEAD~1`)
- `--include-untracked` / `--no-include-untracked` (default: include)
- `--include-staged` / `--no-include-staged` (default: include)
- `--require-git` to fail with exit code `2` instead of falling back to a full scan.

Changed files are collected locally using:

- `git diff --name-only --cached`
- `git diff --name-only`
- `git diff --name-only <since-ref>...HEAD`
- `git ls-files --others --exclude-standard`

### CI recommendation

In CI, pass `--since-ref` from your workflow environment (for example merge-base or base SHA) so incremental scope matches your pipeline policy.

## Local cache

By default, `sdetkit` stores local cache data in `.sdetkit/cache`.

- Override with `--cache-dir PATH`
- Disable with `--no-cache`
- Print per-rule hit/miss stats with `--cache-stats`

Safety model:

- Cache keys include tool version, rule id, repository identity, profile/config hash, and selected packs.
- Rule cache entries include tracked file dependencies plus content digests.
- Cache is only used when dependency manifests are complete and unchanged.
- Unknown dependencies automatically disable cache use for that rule.

## Parallel jobs with deterministic output

Use `--jobs N` to run rules in parallel.

```bash
sdetkit repo audit . --jobs 4 --cache-stats
```

Determinism guarantees:

- Findings/checks are sorted deterministically.
- Output ordering does not depend on completion order.
- Incremental and cache metadata are emitted with stable keys.

## Run record integration

Run records include execution metadata:

- `incremental_used`
- `changed_file_count`
- optional cache summary (hits/misses)

This metadata is included without changing existing finding semantics.
