from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_TEMPLATE_SPECS: dict[str, dict[str, Any]] = {
    "gitlab": {
        "path": "templates/ci/gitlab/day66-advanced-reference.yml",
        "markers": [
            "bash scripts/bootstrap.sh",
            ". .venv/bin/activate",
            "python -m sdetkit",
            "CI_COMMIT_REF_SLUG",
        ],
    },
    "jenkins": {
        "path": "templates/ci/jenkins/day67-advanced-reference.Jenkinsfile",
        "markers": [
            "bash scripts/bootstrap.sh",
            ". .venv/bin/activate",
            "pytest -q",
            "security.sh",
            "PYTHON_VERSION",
        ],
    },
    "tekton": {
        "path": "templates/ci/tekton/day68-self-hosted-reference.yaml",
        "markers": [
            "bash scripts/bootstrap.sh",
            ". .venv/bin/activate",
            "bash ci.sh",
            "bash security.sh",
            "$(params.branch)",
        ],
    },
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _validate_templates(root: Path) -> dict[str, Any]:
    missing: list[str] = []
    checked: list[dict[str, Any]] = []

    for template_id in sorted(_TEMPLATE_SPECS):
        spec = _TEMPLATE_SPECS[template_id]
        rel = str(spec["path"])
        p = root / rel

        if not p.exists():
            missing.append(rel)
            checked.append(
                {
                    "id": template_id,
                    "path": rel,
                    "ok": False,
                    "errors": [f"missing file: {rel}"],
                }
            )
            continue

        content = _read_text(p)
        errors: list[str] = []
        for marker in spec.get("markers", []):
            if marker not in content:
                errors.append(f"missing marker: {marker}")

        checked.append(
            {
                "id": template_id,
                "path": rel,
                "ok": not errors,
                "errors": errors,
            }
        )

    ok = (not missing) and all(item.get("ok") is True for item in checked)
    return {
        "ok": ok,
        "root": str(root),
        "missing": missing,
        "checked": checked,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ci")
    sub = parser.add_subparsers(dest="cmd", required=True)

    vt = sub.add_parser("validate-templates")
    vt.add_argument("--root", default=".", help="Repo root to validate (default: .)")
    vt.add_argument("--format", choices=["text", "json"], default="text")
    vt.add_argument("--strict", action="store_true")
    vt.add_argument("--out", default=None)

    ns = parser.parse_args(list(argv) if argv is not None else None)

    if ns.cmd == "validate-templates":
        root = Path(ns.root).resolve()
        data = _validate_templates(root)
        ok = bool(data.get("ok"))

        if ns.format == "json":
            output = json.dumps(data, sort_keys=True) + "\n"
        else:
            lines = [f"ci template validation: {'PASS' if ok else 'FAIL'}"]
            for item in data.get("checked", []):
                tid = item.get("id")
                path = item.get("path")
                status = "PASS" if item.get("ok") else "FAIL"
                lines.append(f"- {tid}: {status} ({path})")
                for err in item.get("errors", []):
                    lines.append(f"  - {err}")
            if data.get("missing"):
                lines.append("missing:")
                for m in data["missing"]:
                    lines.append(f"- {m}")
            output = "\n".join(lines) + "\n"

        if ns.out:
            Path(ns.out).write_text(output, encoding="utf-8")

        sys.stdout.write(output)

        if ok:
            return 0
        return 2 if ns.strict else 0

    return 2
