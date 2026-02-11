# Patch harness

`Patch harness` is now an official sdetkit feature via `sdetkit patch`.
It applies deterministic, spec-driven edits to files and supports strict check mode for CI.

## Run commands

Preferred (official):

```bash
sdetkit patch spec.json
sdetkit patch spec.json --dry-run
sdetkit patch spec.json --check
```

Backward compatibility wrapper (still supported):

```bash
python tools/patch_harness.py spec.json
```

## Spec format

A spec is a JSON file with a list of files and operations:

```json
{
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

- `path` is relative to the working directory.
- `pattern` is a regular expression.
- `text` supports escaped newlines (`\n`) and tabs (`\t`).

## Idempotency and --check

Operations are designed to be safe for repeated runs.

- `--check` exits `0` if files are already compliant.
- `--check` exits non-zero if changes would be applied.
- `--dry-run` prints a unified diff but does not write files.
- Default mode writes files when changes are needed.

## Indentation token

For insertion operations, `<<INDENT>>` can be used to reuse captured indentation
from a regex group.

Example:

```json
{
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
