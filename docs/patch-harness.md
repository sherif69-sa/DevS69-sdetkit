```markdown
# Patch harness

`tools/patch_harness.py` applies deterministic, spec-driven edits to files.
It supports a strict check mode for CI and repeated runs.

Run it as:

```bash
python tools/patch_harness.py spec.json
python tools/patch_harness.py spec.json --dry-run
python tools/patch_harness.py spec.json --check
````

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

* `path` is relative to the working directory.
* `pattern` is a regular expression.
* `text` supports escaped newlines (`\n`) and tabs (`\t`).

## Idempotency and --check

Operations are designed to be safe for repeated runs.

* `--check` exits `0` if the repo is already compliant.
* `--check` exits non-zero if changes would be applied.
* `--dry-run` prints a unified diff but does not write files.
* Default mode writes files when changes are needed.

## Indentation token

For insertion operations, `<<INDENT>>` can be used to reuse the captured indentation
from the regex pattern group.

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
