# Portfolio readiness (`sdetkit portfolio-readiness`)

Aggregate ship-readiness and enterprise-assessment artifacts across repositories into one risk-ranked portfolio view.

## Manifest format

Provide a JSON array where each item points to existing artifact paths:

```json
[
  {
    "repo": "repo-a",
    "ship_summary": "artifacts/repo-a/ship-readiness-summary.json",
    "enterprise_summary": "artifacts/repo-a/enterprise-assessment-summary.json"
  },
  {
    "repo": "repo-b",
    "ship_summary": "artifacts/repo-b/ship-readiness-summary.json",
    "enterprise_summary": "artifacts/repo-b/enterprise-assessment-summary.json"
  }
]
```

## Run

```bash
python -m sdetkit portfolio-readiness --manifest portfolio-manifest.json --format text
python -m sdetkit portfolio-readiness --manifest portfolio-manifest.json --format json
python -m sdetkit portfolio-readiness --manifest portfolio-manifest.json --format json --out build/portfolio-readiness.json
```

Strict mode fails when any repo is in `critical` priority:

```bash
python -m sdetkit portfolio-readiness --manifest portfolio-manifest.json --strict --format json
```

## Output

- `summary` (repo count, average risk, critical/high counts, go/no-go counts)
- `repos` (risk-ranked rows)
- `top_risks` (top 5 repos for immediate triage)
