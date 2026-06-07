# Adaptive anonymized learning import

Adaptive learning import consumes anonymized organization learning exports without accepting repo-private identifiers. It validates redaction first, then emits local calibration hints that can inform operator review without exposing repository names, paths, notes, or files.

## Command

```bash
python -m sdetkit adaptive learning-import build/sdetkit/anonymized-learning-export.json \
  --format json \
  --out build/sdetkit/adaptive-learning-import.json
```

JSONL records are also accepted when each line is already anonymized.

## Privacy validation

The importer rejects records when:

- private fields such as `repo`, `repository`, `source_path`, `note`, `changed_file_scope`, `affected_files`, or `files` are not `<redacted>`;
- strings look like raw filesystem paths, private file identifiers, URLs, hostnames, or email addresses;
- the input is malformed JSON/JSONL.

## Calibration hints

Accepted imports are grouped by scenario code and produce hints such as:

- `promote` when proof passed or a fix was accepted;
- `review_guardrail` when imported proof failed;
- `examplete` when records are marked false-positive;
- `observe` when evidence is not strong enough to move confidence.

Hints are local-only; they do not mutate built-in scenario packs or enable automatic remediation. Operator feedback hardening now rejects private URLs, hostnames, and email addresses as well as raw paths/files.
