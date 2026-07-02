from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]
AUTHORITY_FIELDS = (
    "reporting_only",
    "automation_allowed",
    "patch_application_allowed",
    "security_dismissal_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)


def _as_dict(value: object) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    rendered = str(value).strip()
    return rendered or default


def adaptive_diagnosis_card(model: JsonObject) -> JsonObject:
    card = _as_dict(model.get("adaptive_diagnosis"))
    if card:
        return card
    primary_failure = _as_dict(model.get("primary_failure"))
    return _as_dict(primary_failure.get("adaptive_diagnosis"))


def _html_list(values: object, *, empty: str) -> str:
    items = [_text(item) for item in _as_list(values) if _text(item)]
    if not items:
        return f"<p>{escape(empty)}</p>"
    rendered = "".join(f"<li><code>{escape(item)}</code></li>" for item in items)
    return f"<ul>{rendered}</ul>"


def render_adaptive_diagnosis_html(card: JsonObject) -> str:
    checks = _as_dict(card.get("checks"))
    check_rows = "".join(
        "<tr>"
        f"<td><code>{escape(_text(name))}</code></td>"
        f"<td>{'Pass' if bool(passed) else 'Missing'}</td>"
        "</tr>"
        for name, passed in checks.items()
    )
    if not check_rows:
        check_rows = '<tr><td colspan="2">No adaptive checks were emitted.</td></tr>'

    authority_rows = "".join(
        "<tr>"
        f"<td><code>{field}</code></td>"
        f"<td>{str(bool(card.get(field, False))).lower()}</td>"
        "</tr>"
        for field in AUTHORITY_FIELDS
    )
    next_action = _text(
        card.get("next_human_action"),
        "Collect exact failure evidence before changing code.",
    )
    completeness = _text(card.get("diagnostic_completeness"), "insufficient").title()
    confidence = _text(card.get("confidence"), "low").title()
    failure_class = (
        _text(card.get("failure_class"), "unknown").replace("_", " ").title()
    )
    decision = "Review first" if bool(card.get("review_first", True)) else "Actionable"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Adaptive Diagnosis</title>
<style>
:root{{color-scheme:light dark;font-family:Inter,ui-sans-serif,system-ui,sans-serif}}
body{{max-width:1100px;margin:0 auto;padding:40px 24px;line-height:1.55}}
header,section{{border:1px solid #7f8ea3;border-radius:18px;padding:24px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}}
.metric{{border:1px solid #7f8ea3;border-radius:14px;padding:16px}}
.metric span{{display:block;font-size:.78rem;text-transform:uppercase;opacity:.72}}
.metric strong{{display:block;margin-top:6px;font-size:1.15rem}}
table{{width:100%;border-collapse:collapse}}
th,td{{padding:10px;border-bottom:1px solid #7f8ea3;text-align:left}}
code{{overflow-wrap:anywhere}}.action{{font-size:1.05rem;font-weight:700}}
</style>
</head>
<body>
<header>
<p><strong>Contributor evidence</strong></p>
<h1>Adaptive Diagnosis</h1>
<p>The first violated contract, its evidence quality, and the exact review-first action.</p>
</header>
<section class="grid">
<div class="metric"><span>Completeness</span><strong>{escape(completeness)}</strong></div>
<div class="metric"><span>Confidence</span><strong>{escape(confidence)}</strong></div>
<div class="metric"><span>Failure class</span><strong>{escape(failure_class)}</strong></div>
<div class="metric"><span>Decision</span><strong>{decision}</strong></div>
</section>
<section>
<h2>Safeguards</h2>
<table><thead><tr><th>Check</th><th>Result</th></tr></thead><tbody>{check_rows}</tbody></table>
</section>
<section>
<h2>Owner files</h2>
{_html_list(card.get("owner_files"), empty="No owner file was resolved.")}
<h2>Focused proof</h2>
{_html_list(card.get("proof_commands"), empty="No focused reproduction command was resolved.")}
<h2>Evidence gaps</h2>
{_html_list(card.get("evidence_gaps"), empty="No evidence gaps were reported.")}
</section>
<section>
<h2>Next human action</h2>
<p class="action">{escape(next_action)}</p>
</section>
<section>
<h2>Authority boundary</h2>
<table><thead><tr><th>Field</th><th>Value</th></tr></thead><tbody>{authority_rows}</tbody></table>
</section>
</body>
</html>
"""


def render_from_model(model: JsonObject) -> str:
    card = adaptive_diagnosis_card(model)
    if not card:
        raise ValueError("review model has no adaptive diagnosis card")
    return render_adaptive_diagnosis_html(card)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a contributor-facing Adaptive Diagnosis artifact."
    )
    parser.add_argument("--review-model", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = json.loads(args.review_model.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("review model must be a JSON object")
    rendered = render_from_model(payload)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered, encoding="utf-8", newline="\n")
    print("adaptive_diagnosis_render=passed")
    print(f"out={args.out.as_posix()}")
    print("reporting_only=true")
    print("automation_allowed=false")
    print("merge_authorized=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
