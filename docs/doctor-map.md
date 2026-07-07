# Doctor work map

This map links the current Doctor bundle surfaces so maintainers can navigate the track quickly.

## Core contract

- Doctor report JSON
- Doctor report Markdown
- Doctor report manifest
- Doctor artifact directory

## CLI surface

The primary command shape is:

```bash
python -m sdetkit doctor --report-contract --report-artifact-dir build/sdetkit
```

## Test surface

Focused tests live around:

- Doctor report CLI behavior
- bundle output filename expectations
- generated artifact directory behavior

## Documentation surface

The documentation set now covers:

- CI usage
- local proof
- status reading
- manifest reading
- maintainer flow

## Next action rule

When a new Doctor change is needed, choose the smallest surface first: contract, CLI, artifact, tests, or docs.
