# pip-audit baseline notes

`dependency-audit.yml` runs:

```bash
pip-audit --format json -o pip-audit-report.json   -r requirements-test.txt   -r requirements-docs.txt
python .github/scripts/check_pip_audit_baseline.py
```

The check fails on any finding not listed in `.github/pip-audit-baseline.json`. The baseline is empty: every advisory the audit reports must be fixed, or reviewed and added there with its package and a note saying when to remove it.

## Removed entries

These were accepted earlier and removed on 2026-11-02, once the pinned versions were past the fix:

| Advisory | Package | Fixed in | Pinned now |
|---|---|---|---|
| CVE-2026-4539 / GHSA-5239-wwwm-4pmq | pygments | 2.20.0 | 2.21.0 |
| CVE-2025-69534 / PYSEC-2026-89 | markdown | 3.8.1 | 3.11.1 |
| CVE-2026-1703 / GHSA-6vgw-5pg2-w6jp | pip | 26.0 | 26.2.2 |
