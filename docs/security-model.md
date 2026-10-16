# Security model

SDETKit is built to be safe to run on a repository it does not trust, and to never act for you:

1. **Review first.** Nothing is applied, merged or dismissed by SDETKit. Every decision artifact records `automation_allowed`, `patch_application_allowed`, `merge_authorized` and `semantic_equivalence_proven` as `false`.
2. **Repository security gate** (`sdetkit security`): offline scanning for risky code and leaked secrets, with a regression baseline.
3. **Guarded local servers**: `sdetkit serve` and `sdetkit ops serve` answer only callers that hold their token.
4. **CI regression checks** on every pull request.

## Threat model assumptions

- The repository may contain untrusted code changes from contributors and automation.
- `gate fast` runs the repository's own tests and tools, so run it on code you would run `pytest` on, and use an isolated environment for code you do not trust.
- CI and local execution stay offline-capable for the core checks.
- Preventing accidental secret leakage and high-risk patterns takes priority over broad heuristic noise.
- Security checks are deterministic, so baselines and diffs are reliable.

## What SDETKit will and will not change

- `gate fast --fix` and `--fix-only` are the only options that edit your files: they run `ruff check --fix` and `ruff format`.
- `diagnose run --prove` applies a candidate fix only in a throwaway copy of the repository and proves it in a second copy; your working tree is never modified, and `diagnose decide --approve` records a decision without applying anything.
- `sdetkit serve` and `sdetkit ops serve` need a bearer token on every request except the health check. They listen on `127.0.0.1` and refuse requests addressed to other host names. Listening on another interface needs `--allow-remote`. See the [tool server](tool-server.md#safety-model).
- `ops` workflows block `shell=true` command steps unless the workflow's policy sets `allow_shell`, and keep file writes inside the artifacts directory unless it sets `allow_artifact_escape`.

## Security gate policy behavior

`python -m sdetkit security` enforces red-flag policy for:

- dangerous execution APIs
- insecure deserialization and YAML loading
- weak hashes
- obvious path traversal / unsafe writes
- secret leakage patterns
- network calls without timeouts
- debug prints in `src/` (except for an explicit allowlist of operational CLI modules)

Allowlists:

- inline: `# sdetkit: allow-security <RULE_ID>`
- repo file: `tools/security_allowlist.json`
- module-level debug print exceptions: `PRINT_ALLOWED_MODULE_SUFFIXES` in `src/sdetkit/gates/security_gate.py`

Baseline regression gate:

- baseline file: `tools/security.baseline.json`
- checks fail only on new findings when baseline exists
- checks fail on all violations when baseline is missing

## Verification

```bash
python -m sdetkit security check --baseline tools/security.baseline.json --format text
python -m sdetkit doctor --ascii
```
