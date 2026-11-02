# First-proof troubleshooting

Use this guide when `make first-proof` or `scripts/first_proof.py` does not produce a clean `SHIP` decision.

## Where to look first

- `build/first-proof/first-proof-summary.json`
- `build/first-proof/gate-fast.stderr.log`
- `build/first-proof/gate-release.stderr.log`
- `build/first-proof/doctor.stderr.log`

The summary now includes:

- `decision` (`SHIP` or `NO-SHIP`)
- `failed_steps`
- `selected_python`

## Common failure signatures and fixes

## 1) Python version mismatch

Signature:

- stderr contains: `requires Python 3.11+`

Fix:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -c constraints-ci.txt -r requirements-test.txt -e .
make first-proof
```

## 2) Contract check runs before summary exists

Signature:

- contract check reports missing summary file

Fix options:

- Required lane (strict):

```bash
make first-proof-verify
```

- Optional parallel lane:

```bash
python scripts/check_first_proof_summary_contract.py \
  --summary build/first-proof/first-proof-summary.json \
  --wait-seconds 60 \
  --allow-missing \
  --format json
```

## 3) Gate returns NO-SHIP

Signature:

- summary shows `decision: "NO-SHIP"`
- `failed_steps` includes `gate-fast` and/or `gate-release`

Fix:

1. Open the failing step logs.
2. Address reported blockers (tests/lint/security/policy).
3. Re-run `make first-proof`.

## 4) Doctor passes but gate steps fail

Interpretation:

- environment and baseline checks may be fine, but release criteria still not met.

Fix:

- treat this as a release-readiness gap; close failing gate conditions and rerun.

## 5) You need smoke mode without hard failure

Use non-strict mode:

```bash
python scripts/first_proof.py --format json --out-dir build/first-proof-smoke
```

Use strict enforcement mode:

```bash
python scripts/first_proof.py --strict --format json --out-dir build/first-proof
```
