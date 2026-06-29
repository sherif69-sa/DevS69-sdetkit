from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "docs/contracts/quality-truth-baseline.v1.json"


def _modules(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {str(item) for item in value}
    return set()


def evaluate_quality_truth(root: Path, contract_path: Path) -> dict[str, object]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    pyproject_text = (root / "pyproject.toml").read_text(encoding="utf-8")
    config = tomllib.loads(pyproject_text)
    overrides = config["tool"]["mypy"]["overrides"]

    blanket = False
    checked: set[str] = set()
    for override in overrides:
        modules = _modules(override.get("module"))
        if modules == {"sdetkit.*"} and override.get("ignore_errors") is True:
            blanket = True
        if override.get("ignore_errors") is False:
            checked.update(name for name in modules if name.startswith("sdetkit."))

    ci_text = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    quality_text = (root / "quality.sh").read_text(encoding="utf-8")
    declared = sorted(set(re.findall(r"Python :: (3\.\d+)", pyproject_text)))
    matrix_match = re.search(r"python-version:\s*\[([^\]]+)\]", ci_text)
    matrix = sorted(set(re.findall(r'"(3\.\d+)"', matrix_match.group(1)))) if matrix_match else []

    typing = contract["typing"]
    runtime = contract["runtime"]
    critical = contract["coverage"]["critical_spine"]
    checks = {
        "blanket_suppression_matches": blanket
        is bool(typing["blanket_package_suppression_present"]),
        "checked_modules_match": checked == set(typing["explicitly_type_checked_modules"]),
        "declared_python_versions_match": declared == sorted(runtime["declared_python_versions"]),
        "canonical_ci_versions_match": matrix == sorted(runtime["canonical_ci_matrix"]),
        "critical_spine_threshold_present": f'COV_FAIL_UNDER: "{critical["minimum_percent"]}"'
        in ci_text,
        "whole_package_scope_exists": 'cov_scope="${COV_SCOPE:-core}"' in quality_text,
        "authority_boundary_preserved": contract["authority_boundary"]
        == {
            "tests_may_be_weakened": False,
            "quality_gates_may_be_hidden": False,
            "unmeasured_quality_may_be_claimed": False,
        },
    }
    return {
        "schema_version": "sdetkit.quality_truth_check.v1",
        "ok": all(checks.values()),
        "checks": checks,
        "observed": {
            "blanket_package_suppression_present": blanket,
            "explicitly_type_checked_modules": sorted(checked),
            "declared_python_versions": declared,
            "canonical_ci_matrix": matrix,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    payload = evaluate_quality_truth(args.root.resolve(), args.contract.resolve())
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if payload["ok"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
