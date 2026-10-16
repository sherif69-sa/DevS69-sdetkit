# Determinism contract

SDETKit's artifacts are meant to be compared, diffed and baselined, so their structure is deterministic.

## Guaranteed deterministic

- Canonical JSON for artifacts and run records (sorted keys, stable formatting).
- `gate fast --stable-json` leaves out timings and machine-specific paths, so two runs on the same commit produce the same JSON.
- Stable ordering of findings, top-N summaries, recurring rules and paths, and history indexes.
- Zip archives (evidence packs, forensics bundles) with sorted entries and fixed timestamps.
- Atomic writes for generated artifacts, so a crash never leaves a partial file.
- HTML escaping of repository-supplied text in rendered reports.

## Not guaranteed deterministic

- Wall-clock timestamps, unless `SOURCE_DATE_EPOCH` is set (honoured by `repo`, `report` and `maintenance` output).
- Timings, and the output of the repository's own tools (pytest, ruff, mypy, `go test`, ...).
- Commands that read the network, such as `intelligence upgrade-audit`.

## Reproducible runs

1. Use `--stable-json` for `gate fast` artifacts you compare or commit.
2. Set `SOURCE_DATE_EPOCH` for stable timestamps.
3. Keep inputs stable and run from a clean tree.
4. Use explicit output paths (`--out`, `--output`, `--history-dir`).
