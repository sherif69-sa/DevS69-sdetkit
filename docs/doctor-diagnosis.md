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
observation_count
prescription_count
severity_counts
diagnoses
observations
prescriptions
next_commands
verification_commands
recommendations
judgment_next_move
source
```

Each failed doctor check becomes a diagnosis with a stable id, category, severity, confidence, safe symptoms, public-safe evidence metadata, prescriptions, next commands, and verification commands.

Quality-only `failed_check_ids` are preserved as observations instead of diagnoses. Diagnosis records are reserved for concrete failed doctor checks so a passing doctor payload does not become a failing diagnosis payload because of auxiliary quality metadata.

The adapter intentionally does not re-emit raw doctor evidence or raw fix text. Raw details remain in the source doctor JSON, while the diagnosis contract records counts and verification commands. This keeps the diagnosis output safe to store in build artifacts and reports.

Use text output for quick terminal summaries:

```bash
python -m sdetkit.doctor_diagnosis --source build/doctor.json --format text
```

This contract is the first Doctor Cortex layer. Future intelligence, adaptive review, five-head review, and Mission Control integration should enrich this diagnosis payload rather than rewriting the doctor core.

CLI and file output use a public-safe projection of the diagnosis contract. The output preserves counts, statuses, severities, categories, and diagnosis ids, but omits raw evidence, raw fix text, nested prescriptions, and source output paths. This keeps generated diagnosis artifacts safe for CI logs, CodeQL-reviewed build output, and reports.

