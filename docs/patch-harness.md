# Patch harness

`Patch harness` is now an official sdetkit feature via `sdetkit patch`.
It applies deterministic, spec-driven edits to files and supports strict check mode for CI.

## Run commands

Preferred (official):

```bash
sdetkit patch spec.json
sdetkit patch spec.json --dry-run
sdetkit patch spec.json --check
sdetkit patch spec.json --root /workspace/myrepo --report-json patch-report.json
sdetkit patch spec.json --max-spec-bytes 1048576
```

Backward compatibility wrapper (still supported):

```bash
python tools/patch_harness.py spec.json
```

## Spec format (versioned)

A spec is a JSON file with `spec_version: 1` and a `files` section. For backward compatibility, omitted `spec_version` is treated as `1`.

List form:

```json
{
  "spec_version": 1,
  "files": [
    {
      "path": "a.txt",
      "ops": [
        { "op": "insert_after", "pattern": "^MARK$", "text": "X\n" }
      ]
    }
  ]
}
```

Dict form (also supported):

```json
{
  "spec_version": 1,
  "files": {
    "a.txt": [
      { "op": "insert_after", "pattern": "^MARK$", "text": "X\n" }
    ]
  }
}
```

- `path` is relative to `--root`.
- default `--root`: git top-level directory when available, else current working directory.
- absolute paths, `..`, empty paths, control bytes, doubled separators, and backslash separators are rejected.
- symlinks are always denied for both target files and parent directories.
- unknown keys in the spec or operation objects are rejected.

## Exit code contract

- `0`: no changes needed or changes applied successfully
- `1`: `--check` detected required changes
- `2`: invalid spec/runtime error/unsafe path/refused operation

## Determinism and safety

- files are processed in sorted order.
- unified diffs are emitted with stable headers.
- writes are atomic (temp file + fsync + replace).
- resource limits are configurable:
  - `--max-files`
  - `--max-bytes-per-file`
  - `--max-total-bytes-changed`
  - `--max-op-count`
  - `--max-spec-bytes`

## Indentation token

For insertion operations, `<<INDENT>>` can be used to reuse captured indentation
from a regex group.

Example:

```json
{
  "spec_version": 1,
  "files": [
    {
      "path": "m.py",
      "ops": [
        {
          "op": "insert_after",
          "pattern": "^([ \t]*)x = 1$",
          "text": "<<INDENT>>y = 2\n"
        }
      ]
    }
  ]
}
```


## SECURITY

The patch harness is root-confined by design:

- every path is validated as a strict relative path under `--root`.
- realpath confinement prevents symlink and traversal escapes.
- if a target file or any parent directory is a symlink, the run fails safely with exit code `2`.
- writes are atomic (`fsync` + `os.replace`) to avoid partial file corruption.
