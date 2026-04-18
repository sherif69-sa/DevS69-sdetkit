# Release confidence flow

This page gives first-time readers a visual map of the release-confidence path in SDETKit.
Primary outcome: consistent ship/no-ship decisions from local runs to CI using artifact-first triage.

```mermaid
flowchart LR
    A[Install / first run] --> B[gate fast]
    B --> C[build/gate-fast.json]
    C --> D[gate release]
    D --> E[build/release-preflight.json]
    E --> F[doctor]
    F --> G[Local to CI continuity]

    G --> H[Engineer]
    G --> I[Reviewer]
    G --> J[Release owner]

    subgraph Triage order
      T1[1) build/release-preflight.json]
      T2[2) build/gate-fast.json]
      T3[3) Raw logs after artifact triage]
      T1 --> T2 --> T3
    end

    E -.inspect first.-> T1
    C -.then inspect.-> T2
```

## How to read this flow

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor
```

Inspect `build/release-preflight.json` first, then `build/gate-fast.json`, and only read raw logs after artifact triage. “Blocked” means one or more release checks did not meet policy, so treat the run as not ready to ship, fix the failing checks, and rerun the same commands.

## Why this helps teams

- Repeatable release decisions.
- Machine-readable evidence.
- Less ad hoc interpretation.
- Smoother handoff across roles.
