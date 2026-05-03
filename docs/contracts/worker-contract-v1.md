# Worker Contract v1

Every worker must emit deterministic JSON with this shape:

```json
{
  "worker": "string",
  "run_id": "string",
  "started_at": "ISO-8601",
  "finished_at": "ISO-8601",
  "status": "ok|fail|error",
  "inputs": {},
  "evidence": [],
  "result": {},
  "escalation": {
    "required": false,
    "reason": "string"
  }
}
```

## Required guarantees

- Idempotent for same inputs.
- Emits machine-readable evidence pointers.
- Emits explicit escalation signal.
- Never returns ambiguous final status.
