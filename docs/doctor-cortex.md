# Doctor Cortex CLI

Doctor Cortex is the structured diagnostic path built on top of the existing doctor command.

```text
doctor JSON -> diagnosis contract -> prescription contract
```

The thin CLI integration keeps the doctor core as the signal collector and delegates contract generation to the adapter modules:

```bash
python -m sdetkit doctor --diagnose --format json --out build/doctor-diagnosis.json
python -m sdetkit doctor --prescribe --format json --out build/doctor-prescriptions.json
```

Use text format for quick local summaries:

```bash
python -m sdetkit doctor --diagnose --format text
python -m sdetkit doctor --prescribe --format text
```

`--diagnose` emits the public Doctor diagnosis contract. `--prescribe` builds the diagnosis contract in memory and emits the public Doctor prescription contract.

The flags are mutually exclusive and support `--format text` or `--format json`. Markdown output remains reserved for the standard doctor report.

The CLI output uses the same public-safe projections as the standalone adapters: raw evidence, raw fix text, private source paths, and input command lists are not re-emitted.
