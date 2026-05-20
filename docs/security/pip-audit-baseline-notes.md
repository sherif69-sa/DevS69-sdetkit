# pip-audit baseline notes

## CVE-2025-69534 / PYSEC-2026-89

`pip-audit` reported `markdown` 3.10.2 for CVE-2025-69534 / PYSEC-2026-89.

The audit report provided no fixed versions for the PYSEC record. The installed version in CI is `markdown` 3.10.2, while the advisory text describes the affected Python-Markdown release as 3.8 and the issue as already fixed after that affected release line.

This repository therefore carries a narrow, reviewed audit baseline for CVE-2025-69534 rather than a dependency upgrade. Remove this baseline when `pip-audit` metadata no longer flags `markdown` 3.10.2 or when a newer actionable fixed version is published.

Verification command:

```bash
pip-audit --format json -o pip-audit-report.json \
  -r requirements-test.txt \
  -r requirements-docs.txt \
  --ignore-vuln CVE-2026-4539 \
  --ignore-vuln CVE-2025-69534
```

Review evidence:

- Package: `markdown`
- Installed version: `3.10.2`
- Audit ID: `PYSEC-2026-89`
- Alias: `CVE-2025-69534`
