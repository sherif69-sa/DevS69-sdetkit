# Repo Audit and Safe Fixes

`sdetkit repo` provides deterministic repository hygiene checks and safe, idempotent auto-fixes.

## Quick start

```bash
sdetkit repo check --format text
sdetkit repo check --format json --out report.json --force
sdetkit repo fix --check --diff
sdetkit repo fix --eol lf
```

## Checks performed (`sdetkit repo check`)

- **UTF-8 decode**: reports files that cannot be decoded as UTF-8.
- **Trailing whitespace**: reports lines ending in spaces/tabs.
- **EOF newline**: reports files missing final newline.
- **Line endings**: reports CRLF, CR, or mixed endings.
- **Hidden/BiDi Unicode**: reports suspicious control/invisible Unicode.
- **Secret scan (regex, deterministic)**:
  - auth/token/api_key/password/cookie style assignments
  - AWS-like access key/secret patterns
  - private key headers (`-----BEGIN ... PRIVATE KEY-----`)

## Exit codes

- `0`: clean / policy pass
- `1`: findings exist and policy requires failure
- `2`: invalid usage, unsafe path, or internal/runtime error

## Safe fixing (`sdetkit repo fix`)

Default safe fixers:

- strip trailing whitespace
- ensure EOF newline
- normalize EOL only when `--eol lf|crlf` is set

Flags:

- `--check`: no writes, prints diff, exits `1` if changes needed
- `--dry-run`: no writes, prints diff, always exits `0`
- `--diff`: always print unified diff
- `--force`: only needed for overwrite-protected outputs

All writes are atomic (`temp + fsync + os.replace`).
