from pathlib import Path

root = Path(__file__).resolve().parents[1]

map_path = root / "docs/docs-map.md"
text = map_path.read_text(encoding="utf-8")
needle = "[Formatter policy proposal eligibility](formatter-policy-proposal.md)"
replacement = (
    needle
    + ", [Formatter policy proposal observation]"
    + "(formatter-policy-proposal-observation.md)"
)
if needle not in text:
    raise SystemExit("docs map formatter proposal marker missing")
text = text.replace(needle, replacement)
map_path.write_text(text, encoding="utf-8")

mkdocs = root / "mkdocs.yml"
text = mkdocs.read_text(encoding="utf-8")
old = "      - Formatter policy proposal eligibility: formatter-policy-proposal.md\n"
new = old + "      - Formatter policy proposal observation: formatter-policy-proposal-observation.md\n"
if text.count(old) != 1:
    raise SystemExit("mkdocs formatter proposal marker mismatch")
mkdocs.write_text(text.replace(old, new), encoding="utf-8")
print("navigation_alignment=applied")
