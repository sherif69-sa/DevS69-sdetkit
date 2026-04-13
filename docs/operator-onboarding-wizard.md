# Operator onboarding wizard

This helper gives a deterministic onboarding summary for the canonical path:

1. `gate fast`
2. `gate release`
3. `doctor`

## Run mode

Use existing artifacts only:

```bash
python scripts/operator_onboarding_wizard.py --format json
```

Force execution of the canonical path before summarizing:

```bash
python scripts/operator_onboarding_wizard.py --run --format json
```

## Output

- `overall_ready`
- `checks` for `gate_fast`, `gate_release`, `doctor` (`state`, `ok`, `failed_steps`)
- `actions` list with next remediation steps
- `run_results` (when `--run` is used)
