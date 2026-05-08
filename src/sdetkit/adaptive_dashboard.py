from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adaptive.dashboard.v1"
ARTIFACT_SPECS = [
    ("diagnosis", "Adaptive diagnosis"),
    ("brief", "Operator brief"),
    ("portfolio", "Portfolio rollup"),
    ("fix_audit", "Fix audit"),
    ("governance", "Enterprise governance"),
    ("adapter", "Integration adapter"),
    ("analytics", "Enterprise analytics"),
    ("remediation_policy", "Remediation policy"),
]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_text(value: Any, limit: int = 180) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _load_artifact(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"read_error={exc}"
    if not text.strip():
        return None, "empty_artifact"
    if path.suffix.lower() in {".json", ".jsonl"}:
        if path.suffix.lower() == ".jsonl":
            rows = []
            for line in text.splitlines():
                if line.strip():
                    rows.append(json.loads(line))
            return {
                "schema_version": "jsonl",
                "record_count": len(rows),
                "records": rows[-5:],
            }, "jsonl"
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload, "json"
        return {"schema_version": "json", "value": payload}, "json"
    return {"schema_version": "text", "preview": _safe_text(text, 600)}, "text"


def _relative_link(path: Path, out_path: Path) -> str:
    try:
        return path.resolve().relative_to(out_path.resolve().parent).as_posix()
    except ValueError:
        try:
            return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
        except ValueError:
            return path.as_posix()


def _summary_fields(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "schema_version": payload.get("schema_version", "unknown"),
    }
    for key in (
        "status",
        "recommendation",
        "ok",
        "risk_score",
        "portfolio_risk_score",
        "repo_count",
        "artifact_count",
        "record_count",
        "finding_count",
        "critical_finding_count",
        "provider",
    ):
        if key in payload:
            fields[key] = payload[key]
    if kind == "diagnosis":
        fields["diagnosis_count"] = payload.get(
            "diagnosis_count", len(_as_list(payload.get("diagnoses")))
        )
        first = _as_dict((_as_list(payload.get("diagnoses")) or [{}])[0])
        if first:
            fields["top_code"] = first.get("code", "UNKNOWN")
    if kind == "analytics":
        metrics = _as_dict(payload.get("metrics"))
        for key in ("remediation_success_rate", "missing_proof_rate", "failed_proof_rate"):
            if key in metrics:
                fields[key] = metrics[key]
    if kind == "portfolio" and _as_list(payload.get("top_risk_scenarios")):
        fields["top_scenario"] = _as_dict(payload["top_risk_scenarios"][0]).get("code")
    if kind == "adapter" and _as_list(payload.get("missing_artifacts")):
        fields["missing_artifacts"] = len(_as_list(payload.get("missing_artifacts")))
    return fields


def build_dashboard(artifact_paths: dict[str, str], *, out_path: Path) -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    for kind, label in ARTIFACT_SPECS:
        raw_path = artifact_paths.get(kind, "")
        if not raw_path:
            missing.append({"kind": kind, "label": label, "reason": "not_configured"})
            artifacts.append(
                {
                    "kind": kind,
                    "label": label,
                    "present": False,
                    "reason": "not_configured",
                }
            )
            continue
        path = Path(raw_path)
        if not path.exists():
            missing.append({"kind": kind, "label": label, "path": raw_path, "reason": "missing"})
            artifacts.append(
                {
                    "kind": kind,
                    "label": label,
                    "path": raw_path,
                    "present": False,
                    "reason": "missing",
                }
            )
            continue
        payload, artifact_format = _load_artifact(path)
        if payload is None:
            missing.append(
                {"kind": kind, "label": label, "path": raw_path, "reason": artifact_format}
            )
            artifacts.append(
                {
                    "kind": kind,
                    "label": label,
                    "path": raw_path,
                    "present": False,
                    "reason": artifact_format,
                }
            )
            continue
        artifacts.append(
            {
                "kind": kind,
                "label": label,
                "path": raw_path,
                "link": _relative_link(path, out_path),
                "present": True,
                "format": artifact_format,
                "summary": _summary_fields(kind, payload),
            }
        )
    present_count = sum(1 for item in artifacts if item.get("present"))
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": present_count > 0,
        "artifact_count": len(artifacts),
        "present_artifact_count": present_count,
        "missing_artifact_count": len(missing),
        "local_only": True,
        "artifacts": artifacts,
        "missing_artifacts": missing,
        "next_owner_action": _next_owner_action(present_count, missing),
    }


def _next_owner_action(present_count: int, missing: list[dict[str, str]]) -> str:
    if present_count == 0:
        return "Generate adaptive artifacts before using the dashboard for release-room review."
    if missing:
        kinds = ", ".join(row["kind"] for row in missing[:4])
        return f"Dashboard is usable with warnings; add missing artifacts next: {kinds}."
    return "Dashboard has all adaptive next-wave artifacts linked for local release-room review."


def render_html(payload: dict[str, Any]) -> str:
    cards: list[str] = []
    for item in _as_list(payload.get("artifacts")):
        row = _as_dict(item)
        label = html.escape(str(row.get("label", row.get("kind", "artifact"))))
        kind = html.escape(str(row.get("kind", "artifact")))
        if not row.get("present"):
            reason = html.escape(str(row.get("reason", "missing")))
            cards.append(
                f'<article class="card missing"><h2>{label}</h2><p class="meta">{kind}</p>'
                f'<p class="status">Missing: {reason}</p></article>'
            )
            continue
        link = html.escape(str(row.get("link", "#")), quote=True)
        summary_items = []
        for key, value in sorted(_as_dict(row.get("summary")).items()):
            summary_items.append(
                f"<li><strong>{html.escape(str(key))}</strong>: {html.escape(_safe_text(value))}</li>"
            )
        cards.append(
            f'<article class="card present"><h2>{label}</h2><p class="meta">{kind}</p>'
            f'<p><a href="{link}">Open local artifact</a></p><ul>{"".join(summary_items)}</ul></article>'
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Adaptive next-wave dashboard</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; color: #172033; background: #f7f8fb; }}
    header {{ margin-bottom: 1.5rem; }}
    .summary {{ display: flex; gap: 1rem; flex-wrap: wrap; }}
    .pill {{ background: white; border: 1px solid #d7dce8; border-radius: 999px; padding: .5rem .9rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem; }}
    .card {{ background: white; border: 1px solid #d7dce8; border-radius: 14px; padding: 1rem; box-shadow: 0 1px 2px rgb(20 30 50 / 8%); }}
    .present {{ border-top: 5px solid #247a3f; }}
    .missing {{ border-top: 5px solid #b25c00; }}
    .meta {{ color: #667085; font-size: .9rem; }}
    .status {{ font-weight: 650; }}
    a {{ color: #175cd3; }}
  </style>
</head>
<body>
  <header>
    <h1>Adaptive next-wave dashboard</h1>
    <p>Deterministic local-only dashboard for adaptive diagnosis, remediation, governance, and analytics artifacts.</p>
    <div class="summary">
      <span class="pill">schema: {html.escape(str(payload.get("schema_version")))}</span>
      <span class="pill">present: {payload.get("present_artifact_count")} / {payload.get("artifact_count")}</span>
      <span class="pill">missing: {payload.get("missing_artifact_count")}</span>
      <span class="pill">local only: {str(payload.get("local_only")).lower()}</span>
    </div>
    <p><strong>Next owner action:</strong> {html.escape(str(payload.get("next_owner_action", "")))}</p>
  </header>
  <main class="grid">
    {"".join(cards)}
  </main>
</body>
</html>
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.adaptive_dashboard")
    for kind, label in ARTIFACT_SPECS:
        parser.add_argument(
            f"--{kind.replace('_', '-')}", default="", help=f"Path to {label} artifact"
        )
    parser.add_argument("--format", choices=["html", "json"], default="html")
    parser.add_argument("--out", default="build/sdetkit/adaptive-dashboard.html")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out_path = Path(str(args.out))
    artifact_paths = {kind: str(getattr(args, kind)) for kind, _label in ARTIFACT_SPECS}
    try:
        payload = build_dashboard(artifact_paths, out_path=out_path)
        rendered = (
            json.dumps(payload, indent=2, sort_keys=True) + "\n"
            if args.format == "json"
            else render_html(payload)
        )
        if args.out:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
