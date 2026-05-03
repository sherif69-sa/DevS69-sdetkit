# Doctor diagnosis contract

Doctor diagnosis converts existing `doctor --format json` output into a stable diagnostic contract.

```bash
python -m sdetkit doctor --format json > build/doctor.json
python -m sdetkit.doctor_diagnosis --source build/doctor.json --out build/doctor-diagnosis.json
```

The diagnosis contract is intentionally an adapter around the existing doctor payload. It does not duplicate doctor checks and does not change release gates.

The JSON output includes:

```text
schema_version
source_schema_version
ok
status
severity
confidence
score
diagnosis_count
prescription_count
severity_counts
diagnoses
prescriptions
next_commands
verification_commands
recommendations
judgment_next_move
source
```

Each failed doctor check becomes a diagnosis with a stable id, category, severity, confidence, symptoms, evidence, prescriptions, next commands, and verification commands.

Use text output for quick terminal summaries:

```bash
python -m sdetkit.doctor_diagnosis --source build/doctor.json --format text
```

This contract is the first Doctor Cortex layer. Future intelligence, adaptive review, five-head review, and Mission Control integration should enrich this diagnosis payload rather than rewriting the doctor core.
