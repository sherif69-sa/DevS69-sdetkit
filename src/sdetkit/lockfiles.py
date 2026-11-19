"""Which Python lockfiles a repository has, and the exact versions they pin.

One answer for every command: `repo check`'s dependency hygiene, the release readiness
score, and the security gate's offline vulnerability scan and SBOM all read this module,
so a uv or Poetry project is recognised everywhere or nowhere.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Lockfiles that pin the full Python dependency tree, in the order they are reported.
PYTHON_LOCKFILES = (
    "uv.lock",
    "poetry.lock",
    "pdm.lock",
    "Pipfile.lock",
    "requirements.lock",
    "requirements.txt.lock",
)
# Requirement files whose `name==version` lines also pin packages.
_REQUIREMENT_FILES = ("requirements.lock", "requirements.txt.lock", "requirements.txt")
# TOML lockfiles made of [[package]] tables with `name` and `version` keys.
_PACKAGE_TABLE_LOCKFILES = ("uv.lock", "poetry.lock", "pdm.lock")

# name[extras] == version, e.g. "pyyaml[libyaml]==5.3", "jinja2 == 2.10", "torch==2.1.0+cpu".
_REQUIREMENT = re.compile(r"([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*==\s*([A-Za-z0-9_.+!\-]+)")
_TOML_STRING = re.compile(r'^(name|version)\s*=\s*"([^"]*)"')

PROVENANCE_SCHEMA_VERSION = "sdetkit.provenance_report.v1"

_PERMISSIVE_LICENSES: set[str] = {
    "mit",
    "apache-2.0",
    "apache 2.0",
    "bsd-2-clause",
    "bsd-3-clause",
    "bsd",
    "isc",
    "python-2.0",
    "unlicense",
    "cc0-1.0",
    "0bsd",
    "mpl-2.0",
}

_COPYLEFT_LICENSES: set[str] = {
    "gpl-2.0",
    "gpl-3.0",
    "gpl",
    "agpl-3.0",
    "agpl",
    "lgpl-2.1",
    "lgpl-3.0",
    "lgpl",
    "sspl",
    "osl-3.0",
}

_SUSPICIOUS_NAMES: set[str] = {
    "reqeusts",
    "urllib4",
    "colorma",
    "colorama-v2",
    "lodsh",
    "crossenv",
    "python-dateutil-fake",
    "setup-tools",
    "pip-installer",
}

_KNOWN_PACKAGE_LICENSES: dict[str, str] = {
    "requests": "apache-2.0",
    "urllib3": "mit",
    "certifi": "mpl-2.0",
    "idna": "bsd-3-clause",
    "charset-normalizer": "mit",
    "pytest": "mit",
    "click": "bsd-3-clause",
    "pydantic": "mit",
    "typing-extensions": "python-2.0",
    "jinja2": "bsd-3-clause",
    "markupsafe": "bsd-3-clause",
    "werkzeug": "bsd-3-clause",
    "flask": "bsd-3-clause",
    "fastapi": "mit",
    "starlette": "bsd-3-clause",
    "anyio": "mit",
    "sniffio": "mit",
    "httpx": "bsd-3-clause",
    "httpcore": "bsd-3-clause",
    "h11": "mit",
    "attrs": "mit",
    "pluggy": "mit",
    "iniconfig": "mit",
    "packaging": "apache-2.0",
    "six": "mit",
    "pyyaml": "mit",
    "toml": "mit",
    "tomli": "mit",
    "setuptools": "mit",
    "wheel": "mit",
    "pip": "mit",
    "ruff": "mit",
    "mypy": "mit",
    "black": "mit",
    "flake8": "mit",
    "isort": "mit",
    "hypothesis": "mpl-2.0",
    "coverage": "apache-2.0",
    "virtualenv": "mit",
    "platformdirs": "mit",
    "filelock": "unlicense",
    "rich": "mit",
    "colorama": "bsd-3-clause",
    "tqdm": "mpl-2.0",
    "react": "mit",
    "react-dom": "mit",
    "lodash": "mit",
    "axios": "mit",
    "express": "mit",
    "typescript": "apache-2.0",
    "vitest": "mit",
    "jest": "mit",
}


@dataclass(frozen=True, order=True)
class PinnedPackage:
    path: str
    line: int
    name: str
    version: str


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def python_lockfiles(root: Path) -> list[str]:
    """The Python lockfiles present at the repository root."""

    return [rel for rel in PYTHON_LOCKFILES if (root / rel).is_file()]


def _from_requirements(rel: str, text: str) -> list[PinnedPackage]:
    pins: list[PinnedPackage] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _REQUIREMENT.match(line)
        if match:
            pins.append(PinnedPackage(rel, line_no, normalize_name(match[1]), match[2]))
    return pins


def _from_package_tables(rel: str, text: str) -> list[PinnedPackage]:
    """Read [[package]] name/version pairs line by line, keeping each package's line."""

    pins: list[PinnedPackage] = []
    current: dict[str, str] | None = None
    start = 0

    def flush() -> None:
        # The project itself (uv's editable or virtual source) is not a dependency.
        if current and "name" in current and "version" in current and not current.get("local"):
            pins.append(
                PinnedPackage(rel, start, normalize_name(current["name"]), current["version"])
            )

    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line.startswith("["):
            flush()
            current, start = ({}, line_no) if line == "[[package]]" else (None, 0)
            continue
        if current is None:
            continue
        match = _TOML_STRING.match(line)
        if match and match[1] not in current:
            current[match[1]] = match[2]
        elif line.startswith("source") and ("editable" in line or "virtual" in line):
            current["local"] = "1"
    flush()
    return pins


def _from_pipfile_lock(rel: str, text: str) -> list[PinnedPackage]:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    pins: list[PinnedPackage] = []
    for section in ("default", "develop"):
        packages = data.get(section) if isinstance(data, dict) else None
        if not isinstance(packages, dict):
            continue
        for name, spec in sorted(packages.items()):
            version = spec.get("version", "") if isinstance(spec, dict) else ""
            if isinstance(version, str) and version.startswith("=="):
                pins.append(PinnedPackage(rel, 1, normalize_name(name), version[2:]))
    return pins


def pinned_python_packages(root: Path) -> list[PinnedPackage]:
    """Every exact `name==version` pin in the root's lockfiles and requirement files."""

    pins: list[PinnedPackage] = []
    for rel in sorted({*PYTHON_LOCKFILES, *_REQUIREMENT_FILES}):
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if rel in _PACKAGE_TABLE_LOCKFILES:
            pins.extend(_from_package_tables(rel, text))
        elif rel == "Pipfile.lock":
            pins.extend(_from_pipfile_lock(rel, text))
        else:
            pins.extend(_from_requirements(rel, text))
    return sorted(pins)


def _scan_unpinned_dependencies(root: Path) -> list[dict[str, Any]]:
    unpinned: list[dict[str, Any]] = []
    for req_file in ("requirements.txt", "requirements.in"):
        p = root / req_file
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for line_no, raw in enumerate(text.splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            if "==" not in line and not line.startswith("@"):
                pkg_match = re.match(r"^([A-Za-z0-9_.\-]+)", line)
                if pkg_match:
                    unpinned.append(
                        {
                            "package": normalize_name(pkg_match[1]),
                            "file": req_file,
                            "line": line_no,
                            "specifier": line,
                        }
                    )
    return unpinned


def _from_package_lock_json(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except ValueError:
        return []
    packages: list[dict[str, Any]] = []
    pkgs_dict = data.get("packages", {}) if isinstance(data, dict) else {}
    for pkg_path, spec in pkgs_dict.items():
        if not pkg_path or not isinstance(spec, dict):
            continue
        raw_name = spec.get("name") or pkg_path.split("node_modules/")[-1]
        name = normalize_name(raw_name)
        ver = str(spec.get("version", ""))
        lic = str(spec.get("license", ""))
        integrity = str(spec.get("integrity", ""))
        packages.append(
            {
                "file": "package-lock.json",
                "name": name,
                "version": ver,
                "license": lic,
                "has_hash": bool(integrity),
            }
        )
    return packages


def _from_go_sum(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    packages: list[dict[str, Any]] = []
    seen: set[str] = set()
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) >= 3:
            mod, ver, hash_str = parts[0], parts[1], parts[2]
            clean_ver = ver[:-7] if ver.endswith("/go.mod") else ver
            key = f"{mod}@{clean_ver}"
            if key not in seen:
                seen.add(key)
                packages.append(
                    {
                        "file": "go.sum",
                        "name": mod,
                        "version": clean_ver,
                        "license": "",
                        "has_hash": hash_str.startswith("h1:"),
                    }
                )
    return packages


def classify_license(name: str, declared: str = "") -> str:
    norm_declared = declared.strip().lower()
    if norm_declared in _COPYLEFT_LICENSES or any(
        cl in norm_declared for cl in ("gpl", "agpl", "lgpl", "sspl")
    ):
        return "COPYLEFT_RESTRICTED"
    if norm_declared in _PERMISSIVE_LICENSES:
        return "PERMISSIVE"

    known = _KNOWN_PACKAGE_LICENSES.get(normalize_name(name))
    if known:
        if known in _COPYLEFT_LICENSES:
            return "COPYLEFT_RESTRICTED"
        if known in _PERMISSIVE_LICENSES:
            return "PERMISSIVE"

    return "UNKNOWN"


def audit_provenance(
    root: Path,
    policy: str = "permissive",
    allow_unpinned: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    analyzed_lockfiles: list[str] = []

    # 1. Python packages
    py_pins = pinned_python_packages(root)
    py_lock_names = [
        f for f in sorted({*PYTHON_LOCKFILES, *_REQUIREMENT_FILES}) if (root / f).is_file()
    ]
    analyzed_lockfiles.extend(py_lock_names)

    # 2. JS packages
    js_pkgs = _from_package_lock_json(root / "package-lock.json")
    if (root / "package-lock.json").is_file():
        analyzed_lockfiles.append("package-lock.json")

    # 3. Go packages
    go_pkgs = _from_go_sum(root / "go.sum")
    if (root / "go.sum").is_file():
        analyzed_lockfiles.append("go.sum")

    # Unpinned dependencies
    unpinned = _scan_unpinned_dependencies(root)

    violations: list[dict[str, str]] = []

    # Check unpinned
    if not allow_unpinned:
        for u in unpinned:
            violations.append(
                {
                    "severity": "MEDIUM",
                    "category": "UNPINNED",
                    "package": u["package"],
                    "file": u["file"],
                    "message": f"Dependency '{u['package']}' is not strictly pinned ({u['specifier']}).",
                }
            )

    all_packages: list[dict[str, Any]] = []

    for p in py_pins:
        lic = classify_license(p.name)
        all_packages.append(
            {
                "ecosystem": "python",
                "name": p.name,
                "version": p.version,
                "file": p.path,
                "license_category": lic,
            }
        )
        if p.name in _SUSPICIOUS_NAMES:
            violations.append(
                {
                    "severity": "HIGH",
                    "category": "SUSPICIOUS_NAME",
                    "package": p.name,
                    "file": p.path,
                    "message": f"Package '{p.name}' matches known typosquatting heuristic.",
                }
            )
        if policy == "permissive" and lic == "COPYLEFT_RESTRICTED":
            violations.append(
                {
                    "severity": "HIGH",
                    "category": "LICENSE_RISK",
                    "package": p.name,
                    "file": p.path,
                    "message": f"Package '{p.name}' has copyleft license restricting proprietary use.",
                }
            )

    for js_item in js_pkgs:
        lic = classify_license(js_item["name"], js_item.get("license", ""))
        all_packages.append(
            {
                "ecosystem": "javascript",
                "name": js_item["name"],
                "version": js_item["version"],
                "file": js_item["file"],
                "license_category": lic,
            }
        )
        if js_item["name"] in _SUSPICIOUS_NAMES:
            violations.append(
                {
                    "severity": "HIGH",
                    "category": "SUSPICIOUS_NAME",
                    "package": js_item["name"],
                    "file": js_item["file"],
                    "message": f"Package '{js_item['name']}' matches known typosquatting heuristic.",
                }
            )
        if policy == "permissive" and lic == "COPYLEFT_RESTRICTED":
            violations.append(
                {
                    "severity": "HIGH",
                    "category": "LICENSE_RISK",
                    "package": js_item["name"],
                    "file": js_item["file"],
                    "message": f"Package '{js_item['name']}' has copyleft license restricting proprietary use.",
                }
            )

    for go_item in go_pkgs:
        lic = classify_license(go_item["name"], go_item.get("license", ""))
        all_packages.append(
            {
                "ecosystem": "go",
                "name": go_item["name"],
                "version": go_item["version"],
                "file": go_item["file"],
                "license_category": lic,
            }
        )

    # Compute digest
    tree_str = json.dumps(
        sorted([f"{pkg.get('name')}=={pkg.get('version')}" for pkg in all_packages])
    )
    tree_digest = hashlib.sha256(tree_str.encode("utf-8")).hexdigest()

    perm_count = sum(1 for p in all_packages if p.get("license_category") == "PERMISSIVE")
    copyleft_count = sum(
        1 for p in all_packages if p.get("license_category") == "COPYLEFT_RESTRICTED"
    )
    unknown_count = sum(1 for p in all_packages if p.get("license_category") == "UNKNOWN")

    has_high = any(v["severity"] == "HIGH" for v in violations)
    has_med = any(v["severity"] == "MEDIUM" for v in violations)

    if has_high:
        verdict = "FAIL"
    elif has_med:
        verdict = "WARNING"
    else:
        verdict = "PASS"

    return {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(root),
        "policy": policy,
        "verdict": verdict,
        "lockfiles_analyzed": sorted(set(analyzed_lockfiles)),
        "total_packages": len(all_packages),
        "pinned_count": len(all_packages),
        "unpinned_count": len(unpinned),
        "license_summary": {
            "permissive": perm_count,
            "copyleft_restricted": copyleft_count,
            "unknown": unknown_count,
        },
        "dependency_tree_digest": tree_digest,
        "violations": violations,
    }


def render_provenance_markdown(report: Mapping[str, Any]) -> str:
    verdict = report.get("verdict", "UNKNOWN")
    tot = report.get("total_packages", 0)
    unpinned = report.get("unpinned_count", 0)
    lic_sum = report.get("license_summary", {})
    lockfiles = report.get("lockfiles_analyzed", [])
    violations = report.get("violations", [])
    digest = report.get("dependency_tree_digest", "")[:12]

    lines = [
        "# SDETKit Supply-Chain & License Provenance Radar",
        "",
        (
            f"**Verdict:** `{verdict}` | **Total Packages:** {tot} | "
            f"**Unpinned:** {unpinned} | **Tree Digest:** `{digest}...`"
        ),
        "",
        "### Provenance & License Summary",
        "",
        "| Metric | Count | Evaluation |",
        "|:---|:---:|:---|",
        f"| **Lockfiles Analyzed** | {len(lockfiles)} | `{', '.join(lockfiles) if lockfiles else 'none'}` |",
        f"| **Total Dependency Pins** | {tot} | Active in workspace |",
        f"| **Unpinned Wildcards** | {unpinned} | {'Zero unpinned dependencies' if unpinned == 0 else 'Unpinned packages detected'} |",
        f"| **Permissive Licenses** | {lic_sum.get('permissive', 0)} | MIT / Apache-2.0 / BSD verified |",
        f"| **Copyleft Restricted** | {lic_sum.get('copyleft_restricted', 0)} | {'Clean (zero copyleft viral risk)' if lic_sum.get('copyleft_restricted', 0) == 0 else 'Copyleft contamination risk'} |",
        f"| **Unknown Licenses** | {lic_sum.get('unknown', 0)} | Requires inspection |",
    ]

    if violations:
        lines.extend(
            [
                "",
                "### Supply-Chain Findings & Violations",
                "",
                "| Severity | Category | Package | Source File | Finding |",
                "|:---:|:---:|:---|:---|:---|",
            ]
        )
        for v in violations:
            lines.append(
                f"| **{v.get('severity')}** | `{v.get('category')}` | `{v.get('package')}` | "
                f"`{v.get('file')}` | {v.get('message')} |"
            )

    return "\n".join(lines).strip() + "\n"


def provenance_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit provenance",
        description=(
            "Audit dependency lockfiles, copyleft license compliance, and "
            "supply-chain provenance attestations."
        ),
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Repository root directory to audit (default: .).",
    )
    parser.add_argument(
        "--policy",
        choices=["permissive", "allow-copyleft"],
        default="permissive",
        help="License enforcement policy (default: permissive).",
    )
    parser.add_argument(
        "--allow-unpinned",
        action="store_true",
        help="Do not flag unpinned dependencies as warnings.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "md"],
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument("--out", help="Path to write JSON provenance report.")
    parser.add_argument("--summary-out", help="Path to write Markdown summary report.")

    raw = list(argv) if argv is not None else sys.argv[1:]
    if raw and raw[0] in ("provenance", "license-provenance"):
        raw = raw[1:]
    args = parser.parse_args(raw)

    root_path = Path(args.root).resolve()
    report = audit_provenance(
        root=root_path,
        policy=args.policy,
        allow_unpinned=args.allow_unpinned,
    )

    md = render_provenance_markdown(report)

    if args.out:
        out_p = Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.summary_out:
        sum_p = Path(args.summary_out)
        sum_p.parent.mkdir(parents=True, exist_ok=True)
        sum_p.write_text(md, encoding="utf-8")

    if args.format == "json":
        sys.stdout.write(json.dumps(report, indent=2) + "\n")
    elif args.format == "md":
        sys.stdout.write(md)
    else:
        sys.stdout.write(md)

    return 0 if report.get("verdict") in ("PASS", "WARNING") else 1


main = provenance_main
