# Doctor prescriptions

Doctor prescriptions convert the public Doctor diagnosis contract into public-safe remediation guidance.

```bash
python -m sdetkit doctor --format json > build/doctor.json
python -m sdetkit.doctor_diagnosis --source build/doctor.json --out build/doctor-diagnosis.json
python -m sdetkit.doctor_prescriptions --source build/doctor-diagnosis.json --out build/doctor-prescriptions.json
```

The prescription contract is intentionally a second adapter layer. It does not re-run doctor checks and does not modify release gates.

The JSON output includes:

```text
schema_version
source_schema_version
ok
status
severity
confidence
prescription_count
severity_counts
prescriptions
next_commands
verification_commands
source
```

Each prescription is generated from allowlisted guidance templates keyed by known doctor diagnosis ids. Raw diagnosis evidence, raw fix text, private source paths, and command lists from the input JSON are not re-emitted.

Use text output for quick terminal summaries:

```bash
python -m sdetkit.doctor_prescriptions --source build/doctor-diagnosis.json --format text
```

This is the second Doctor Cortex layer:

```text
doctor JSON -> diagnosis contract -> prescription contract
```

Future adaptive review, five-head review, intelligence matching, and Mission Control integration should enrich these public-safe prescription objects instead of rewriting the doctor core.
