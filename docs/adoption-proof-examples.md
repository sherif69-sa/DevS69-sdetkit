# Adoption-proof examples

These examples show realistic, artifact-first usage that maps to day-to-day PR and release review flow.

Canonical artifact-producing run:

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor
```

## Example 1: Team runs `gate fast`, `gate release`, `doctor`

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor
```

Why this sequence works:
- `gate fast` gives immediate pre-merge signal.
- `gate release` gives release-level aggregate decision input.
- `doctor` validates runtime/setup assumptions that can explain unexpected failures.

## Example 2: Artifact-first triage path

Use this deterministic order:
1. Read `build/release-preflight.json`.
2. If `failed_steps` includes `gate_fast`, read `build/gate-fast.json`.
3. Only then inspect raw logs for low-level details.

This keeps triage focused on explicit machine-readable decision points.

## Example 3: What blocked

A practical blocked state looks like:
- `release-preflight.json` has `ok: false`
- `failed_steps` is non-empty
- failure points to the next deterministic remediation target

At this stage, the team has enough structure to decide “not ready yet” without narrative guesswork.

## Example 4: What to fix next

Teams can choose the next action from the first failing artifact field instead of broad, unfocused investigation.

Typical next-step pattern:
- fix the earliest failing gate condition
- re-run `gate fast`
- re-run `gate release`
- keep `doctor` clean before final review

## Example 5: How this helps real review/release flow

In practical review operations:
- engineers attach artifact outputs in PR context
- reviewers validate `ok` / `failed_steps` quickly
- release owners use the same outputs for go/no-go calls

This creates a single evidence thread from implementation review through release decision, without changing core repo workflows.
