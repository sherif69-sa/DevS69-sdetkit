from pathlib import Path

path = Path(__file__).resolve().parents[1] / "docs/roadmap/product-roadmap.md"
text = path.read_text(encoding="utf-8")

old = "- `docs/contracts/remediation-research.v1.json`\n"
new = (
    old
    + "- `docs/contracts/formatter-policy-proposal-observation.v1.json`\n"
    + "- `build/formatter-policy-proposal-observation/formatter-policy-proposal-observation.json`\n"
)
if text.count(old) != 1:
    raise SystemExit("roadmap artifact marker mismatch")
text = text.replace(old, new)

old = "| Formatter policy proposal eligibility | Provider-bound human approval"
insert = (
    "| Formatter policy proposal observation | A versioned reporting-only contract retains "
    "digest-bound reviewer decisions and proposal-quality metrics. |\n"
)
position = text.find(old)
if position < 0:
    raise SystemExit("roadmap completed-lane marker missing")
line_end = text.find("\n", position)
text = text[: line_end + 1] + insert + text[line_end + 1 :]

text = text.replace(
    "formatter_policy_proposal_observation",
    "formatter_policy_proposal_reviewed_evidence",
)
text = text.replace(
    "conditional narrow policy consideration",
    "one source-backed reviewed proposal observation",
)
text = text.replace(
    "Continue reviewed evidence collection without broad maturity claims while advancing guarded remediation research.",
    "Retain one real reviewed formatter proposal observation before later execution research.",
)
path.write_text(text, encoding="utf-8")
print("roadmap_delta=applied")
