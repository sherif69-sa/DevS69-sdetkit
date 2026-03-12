# Evidence Pack

`evidence` is an audit-grade artifact command surface with deterministic packaging and verification.

## Commands

- `python3 -m sdetkit evidence pack --output .sdetkit/out/evidence.zip`
- `python3 -m sdetkit evidence validate .sdetkit/out/evidence.zip --format json`
- `python3 -m sdetkit evidence compare old.zip new.zip --format json`

## Contract

- JSON responses include `schema_version: sdetkit.evidence.v2`.
- Deterministic zip ordering and fixed file timestamps are enforced.
- `manifest.json` includes deterministic checksum list for every packed artifact.
- Exit codes:
  - `0`: success
  - `2`: validation or input error

## Real-world use

1. Build evidence for release governance (`pack`).
2. Validate integrity in CI before publishing (`validate`).
3. Compare two evidence packs for drift during incident review (`compare`).

## Sample artifacts

- `.sdetkit/out/evidence.zip`
- `.sdetkit/out/manifest.json`

Example manifest excerpt:

```json
{
  "schema_version": "sdetkit.evidence.v2",
  "version": 2,
  "redacted": false,
  "files": [
    {"path": "doctor.txt", "sha256": "..."}
  ]
}
```
