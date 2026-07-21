from pathlib import Path

path = Path(__file__).resolve().parents[1] / "docs/operator-reviewed-kpi-portfolio-report.md"
text = path.read_text(encoding="utf-8")

replacements = [
    (
        "build/sdetkit/adoption-product-kpi-report.json\n",
        "build/sdetkit/adoption-product-kpi-report.json\n"
        "build/formatter-policy-proposal-observation/formatter-policy-proposal-observation.json\n",
    ),
    (
        "  --kpi-report-json build/sdetkit/adoption-product-kpi-report.json \\\n  --out",
        "  --kpi-report-json build/sdetkit/adoption-product-kpi-report.json \\\n"
        "  --proposal-observation-report-json build/formatter-policy-proposal-observation/formatter-policy-proposal-observation.json \\\n"
        "  --out",
    ),
    (
        "Freshness binds the output to the exact bytes of the radar, KPI report, capability matrix, roadmap, operator guide, generator, and current Git head.",
        "Freshness also binds the formatter proposal observation report to the current Git head.",
    ),
    (
        "reviewed_kpi_evidence\ncapability_matrix",
        "reviewed_kpi_evidence\nformatter_policy_proposal_observation\ncapability_matrix",
    ),
    (
        "`formatter_policy_proposal_observation`",
        "`formatter_policy_proposal_reviewed_evidence`",
    ),
]
for old, new in replacements:
    if text.count(old) < 1:
        raise SystemExit(f"operator marker missing: {old[:70]!r}")
    text = text.replace(old, new)

marker = "## Decision rule\n"
addition = (
    "## Formatter proposal observation\n\n"
    "The repository-owned source currently contains zero reviewed proposal records. "
    "The fresh report therefore requires one real digest-bound review and keeps "
    "`false_authority_count=0`. Synthetic fixtures are not accepted as product evidence.\n\n"
)
if text.count(marker) != 1:
    raise SystemExit("operator decision marker mismatch")
text = text.replace(marker, addition + marker)
path.write_text(text, encoding="utf-8")
print("operator_delta=applied")
