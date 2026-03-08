# Ready-to-use setup (start working in minutes)

Use this guide when you want a practical, production-focused start without learning the entire repository first.

## Fast start (recommended)

```bash
bash scripts/ready_to_use.sh quick
```

What this does:

1. Bootstraps the local environment.
2. Verifies the SDETKit CLI is available.
3. Runs the CI quick lane.
4. Leaves you with a working repo and a clear next step.

## Full release-confidence start

```bash
bash scripts/ready_to_use.sh release
```

In addition to the fast start, this mode runs:

- `bash quality.sh cov`
- `python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0`
- `python -m sdetkit gate release`

Use this when you need production-quality release evidence.

## Command behavior

- Exit code `0`: setup/checks completed successfully.
- Non-zero exit code: setup or checks failed; review the command output and fix the first failing step.

## Next actions after setup

- Explore command groups: `python -m sdetkit --help`
- See playbooks: `python -m sdetkit playbooks`
- Read strategy context:
  - `docs/product-strategy.md`
  - `docs/global-production-transformation-playbook.md`
