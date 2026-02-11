from __future__ import annotations

import argparse
import ast
import datetime as dt
import difflib
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .atomicio import atomic_write_text
from .security import SecurityError, safe_path

SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".hypothesis",
        ".nox",
        ".tox",
        ".venv",
        "venv",
        "node_modules",
    }
)

SKIP_FILES: frozenset[str] = frozenset({".coverage"})

BIDI_HIDDEN_CODEPOINTS: frozenset[str] = frozenset(
    {
        "\u200b",  # zero width space
        "\u200c",  # zero width non-joiner
        "\u200d",  # zero width joiner
        "\ufeff",  # zero width no-break space (BOM)
        "\u202a",  # LRE
        "\u202b",  # RLE
        "\u202c",  # PDF
        "\u202d",  # LRO
        "\u202e",  # RLO
        "\u2066",  # LRI
        "\u2067",  # RLI
        "\u2068",  # FSI
        "\u2069",  # PDI
    }
)

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "auth_header",
        re.compile(
            r"(?i)\\b(?:authorization|x-api-key|api[_-]?key|token|password|cookie|set-cookie)\\b\\s*[:=]\\s*[^\\s]{4,}"
        ),
    ),
    ("aws_access_key", re.compile(r"\\bAKIA[0-9A-Z]{16}\\b")),
    (
        "aws_secret_key",
        re.compile(r"(?i)aws(.{0,20})?(?:secret|access).{0,5}[=:].{0,5}[A-Za-z0-9/+=]{40}"),
    ),
    (
        "private_key_header",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    ("github_pat", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9._-]+\.[A-Za-z0-9._-]+\b")),
)

HIGH_ENTROPY_TOKEN = re.compile(r"\b[A-Za-z0-9+/=_-]{24,}\b")
SENSITIVE_WORDS = (
    "secret",
    "token",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "auth",
    "credential",
)
WORKFLOW_USE_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s]+)\s*$")
UNPINNED_DEP_RE = re.compile(r"^(?:[A-Za-z0-9_.-]+)(?:\[[^\]]+\])?\s*(?:>=|>|~=|\*|$)")
PRIVATE_KEY_FILES: frozenset[str] = frozenset({"id_rsa", "id_dsa"})
PRIVATE_KEY_SUFFIXES: tuple[str, ...] = (".pem", ".p12", ".pfx", ".key")
_UTC = getattr(dt, "UTC", dt.timezone.utc)  # noqa: UP017


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = {ch: s.count(ch) for ch in set(s)}
    n = float(len(s))
    entropy = 0.0
    for count in counts.values():
        p = count / n
        entropy -= p * (0 if p == 0 else math.log2(p))
    return entropy


def _safe_snippet(line: str) -> str:
    if len(line) <= 10:
        return "<redacted>"
    return f"{line[:3]}...{line[-3:]}"
    return f"{line[:3]}…{line[-3:]}"


def _git_commit_sha(root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    sha = proc.stdout.strip()
    return sha if proc.returncode == 0 and sha else None


def _changed_files(root: Path, base: str) -> set[str]:
    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "diff",
                "--name-only",
                "--diff-filter=ACMRTUXB",
                f"{base}...HEAD",
            ],
            ["git", "-C", str(root), "diff", "--name-only", "--diff-filter=ACMRTUXB", f"{base}...HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return set()
    if proc.returncode != 0:
        return set()
    return {x.strip() for x in proc.stdout.splitlines() if x.strip()}


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    path: str
    line: int
    column: int
    code: str
    message: str
    confidence: str = "medium"
    remediation: str = ""
    snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "confidence": self.confidence,
            "remediation": self.remediation,
            "snippet": self.snippet,
        }


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info")
        )
        for fname in sorted(filenames):
            if fname in SKIP_FILES:
                continue
            p = Path(dirpath) / fname
            if p.is_file():
                files.append(p)
    files.sort(key=lambda x: x.relative_to(root).as_posix())
    return files


def _line_for_offset(text: str, offset: int) -> tuple[int, int]:
    prefix = text[:offset]
    line = prefix.count("\n") + 1
    last_nl = prefix.rfind("\n")
    col = offset + 1 if last_nl == -1 else offset - last_nl
    return line, col


def run_checks(
    root: Path,
    *,
    profile: str,
    changed_only: bool,
    diff_base: str,
    baseline: list[dict[str, Any]],
) -> list[Finding]:
    findings: list[Finding] = []
    only = _changed_files(root, diff_base) if changed_only else set()

    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        if only and rel not in only:
            continue
        try:
            data = path.read_bytes()
        except OSError as exc:
            findings.append(
                Finding("decode", "error", rel, 1, 1, "read_error", f"unable to read file: {exc}")
            )
            continue

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            findings.append(
                Finding(
                    "decode",
                    "error",
                    rel,
                    1,
                    1,
                    "utf8_decode",
                    f"invalid UTF-8 at byte {exc.start}: {exc.reason}",
                    remediation="re-encode file as UTF-8 text",
                )
            )
            continue

        if b"\r\n" in data and b"\n" in data.replace(b"\r\n", b""):
            findings.append(
                Finding(
                    "line_endings", "warn", rel, 1, 1, "mixed_eol", "mixed line endings detected"
                )
            )
        elif b"\r\n" in data:
            findings.append(
                Finding("line_endings", "warn", rel, 1, 1, "crlf_eol", "CRLF line endings detected")
            )
        elif b"\r" in data:
            findings.append(
                Finding(
                    "line_endings", "warn", rel, 1, 1, "cr_eol", "legacy CR line endings detected"
                )
            )

        lines = text.splitlines(keepends=True)
        for idx, text_row in enumerate(lines, start=1):
            content = text_row.rstrip("\r\n")
            stripped = content.rstrip(" \t")
            if content != stripped:
                findings.append(
                    Finding(
                        "trailing_whitespace",
                        "warn",
                        rel,
                        idx,
                        len(stripped) + 1,
                        "trailing_ws",
                        "trailing whitespace",
                        confidence="high",
                        remediation="remove trailing spaces/tabs",
                    )
                )

        if data and not data.endswith(b"\n"):
            findings.append(
                Finding(
                    "eof_newline",
                    "warn",
                    rel,
                    max(1, len(lines)),
                    1,
                    "missing_eof_nl",
                    "missing EOF newline",
                    confidence="high",
                    remediation="add a single newline at end-of-file",
                )
            )

        for i, ch in enumerate(text):
            if ch in BIDI_HIDDEN_CODEPOINTS:
                line, col = _line_for_offset(text, i)
                findings.append(
                    Finding(
                        "hidden_unicode",
                        "error",
                        rel,
                        line,
                        col,
                        "hidden_unicode",
                        f"hidden/bidi Unicode character U+{ord(ch):04X}",
                        confidence="high",
                        remediation="remove invisible bidi control characters",
                    )
                )

        for idx, text_line in enumerate(text.splitlines(), start=1):
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(text_line):
                    findings.append(
                        Finding(
                            "secret_scan",
                            "error",
                            rel,
                            idx,
                            1,
                            label,
                            f"potential secret matched pattern: {label}",
                            confidence="high",
                            remediation="remove secret and load it from secure secret manager",
                            snippet=_safe_snippet(text_line),
                        )
                    )

            if any(w in text_line.lower() for w in SENSITIVE_WORDS):
                for tok in HIGH_ENTROPY_TOKEN.findall(text_line):
                    if _shannon_entropy(tok) >= 4.0:
                        findings.append(
                            Finding(
                                "secret_scan",
                                "error",
                                rel,
                                idx,
                                text_line.find(tok) + 1,
                                "high_entropy_secret",
                                "high-entropy token near sensitive keyword",
                                confidence="medium",
                                remediation="rotate and remove token from source",
                                snippet=_safe_snippet(tok),
                            )
                        )

            lower = text_line.lower().replace(" ", "")
            config_like = rel.endswith(
                (".env", ".ini", ".cfg", ".conf", ".toml", ".yaml", ".yml", ".json")
            )
            if config_like and ("debug=true" in lower or "allow_all_origins=true" in lower):
            if "debug=true" in lower or "allow_all_origins=true" in lower:
                findings.append(
                    Finding(
                        "config_hardening",
                        "warn",
                        rel,
                        idx,
                        1,
                        "dangerous_default",
                        "dangerous debug or allow-all default detected",
                        confidence="high",
                        remediation="disable debug and restrict origin permissions",
                    )
                )

        if profile == "enterprise" and rel.endswith(".py"):
            findings.extend(_scan_python_ast(rel, text))

        if (
            profile == "enterprise"
            and rel.startswith(".github/workflows/")
            and rel.endswith((".yml", ".yaml"))
        ):
        if profile == "enterprise" and rel.startswith(".github/workflows/") and rel.endswith((".yml", ".yaml")):
            findings.extend(_scan_workflow(rel, text))

        if path.name in PRIVATE_KEY_FILES or path.suffix.lower() in PRIVATE_KEY_SUFFIXES:
            findings.append(
                Finding(
                    "config_leak",
                    "error",
                    rel,
                    1,
                    1,
                    "private_key_file",
                    "private key or certificate material committed",
                    confidence="high",
                    remediation="remove file from git history and rotate impacted credentials",
                )
            )

        if path.name in {".env", ".pypirc", ".npmrc", "config.json"}:
            findings.append(
                Finding(
                    "config_leak",
                    "error",
                    rel,
                    1,
                    1,
                    "sensitive_config_file",
                    "sensitive runtime config file committed",
                    confidence="medium",
                    remediation="avoid committing secrets-bearing config files",
                )
            )

    if profile == "enterprise":
        findings.extend(_scan_dependency_hygiene(root, only if changed_only else None))

    findings = _apply_baseline(findings, baseline)

    findings.sort(key=lambda f: (f.path, f.line, f.column, f.check, f.code, f.message))
    return findings


def _scan_python_ast(rel: str, text: str) -> list[Finding]:
    out: list[Finding] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = f"{getattr(node.func.value, 'id', '')}.{node.func.attr}".lstrip(".")
            if name in {"eval", "exec", "pickle.loads", "yaml.load"}:
                out.append(
                    Finding(
                        "code_risk",
                        "error",
                        rel,
                        node.lineno,
                        node.col_offset + 1,
                        name.replace(".", "_"),
                        f"unsafe call: {name}",
                        remediation="use safer alternatives",
                    )
                )
            if name == "subprocess.run" or name == "subprocess.Popen":
                for kw in node.keywords:
                    if (
                        kw.arg == "shell"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                    ):
                        out.append(
                            Finding(
                                "code_risk",
                                "error",
                                rel,
                                node.lineno,
                                node.col_offset + 1,
                                "subprocess_shell_true",
                                "subprocess with shell=True",
                                remediation="pass argv list and keep shell=False",
                            )
                        )
                out.append(Finding("code_risk", "error", rel, node.lineno, node.col_offset + 1, name.replace(".", "_"), f"unsafe call: {name}", remediation="use safer alternatives"))
            if name == "subprocess.run" or name == "subprocess.Popen":
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        out.append(Finding("code_risk", "error", rel, node.lineno, node.col_offset + 1, "subprocess_shell_true", "subprocess with shell=True", remediation="pass argv list and keep shell=False"))
    return out


def _scan_workflow(rel: str, text: str) -> list[Finding]:
    out: list[Finding] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        m = WORKFLOW_USE_RE.match(line)
        if m:
            uses = m.group(1)
            if "@" in uses and re.search(r"@[0-9a-f]{40}$", uses) is None:
                out.append(
                    Finding(
                        "gha_hardening",
                        "warn",
                        rel,
                        idx,
                        1,
                        "unpinned_action",
                        "GitHub Action is not pinned to full commit SHA",
                        remediation="pin action with @<40-char-SHA>",
                    )
                )
        lower = line.lower()
        if "pull_request_target" in lower:
            out.append(
                Finding(
                    "gha_hardening",
                    "error",
                    rel,
                    idx,
                    1,
                    "pull_request_target",
                    "pull_request_target requires strict hardening",
                    remediation="prefer pull_request unless privileged flow is required",
                )
            )
        if "permissions: write-all" in lower:
            out.append(
                Finding(
                    "gha_hardening",
                    "error",
                    rel,
                    idx,
                    1,
                    "write_all_permissions",
                    "workflow uses write-all permissions",
                    remediation="use least privilege permissions block",
                )
            )
        if "curl" in lower and "|" in lower and "bash" in lower:
            out.append(
                Finding(
                    "gha_hardening",
                    "error",
                    rel,
                    idx,
                    1,
                    "curl_bash",
                    "curl|bash pattern in workflow",
                    remediation="download, verify checksum/signature, then execute",
                )
            )
                out.append(Finding("gha_hardening", "warn", rel, idx, 1, "unpinned_action", "GitHub Action is not pinned to full commit SHA", remediation="pin action with @<40-char-SHA>"))
        lower = line.lower()
        if "pull_request_target" in lower:
            out.append(Finding("gha_hardening", "error", rel, idx, 1, "pull_request_target", "pull_request_target requires strict hardening", remediation="prefer pull_request unless privileged flow is required"))
        if "permissions: write-all" in lower:
            out.append(Finding("gha_hardening", "error", rel, idx, 1, "write_all_permissions", "workflow uses write-all permissions", remediation="use least privilege permissions block"))
        if "curl" in lower and "|" in lower and "bash" in lower:
            out.append(Finding("gha_hardening", "error", rel, idx, 1, "curl_bash", "curl|bash pattern in workflow", remediation="download, verify checksum/signature, then execute"))
    return out


def _scan_dependency_hygiene(root: Path, only: set[str] | None) -> list[Finding]:
    out: list[Finding] = []
    has_py_manifest = (root / "pyproject.toml").exists() or (root / "requirements.txt").exists()
    has_node_manifest = (root / "package.json").exists()
    if has_py_manifest and not ((root / "poetry.lock").exists() or (root / "uv.lock").exists()):
        if only is None or "pyproject.toml" in only or "requirements.txt" in only:
            out.append(
                Finding(
                    "dependency_hygiene",
                    "warn",
                    "pyproject.toml",
                    1,
                    1,
                    "missing_python_lockfile",
                    "Python manifest found without lockfile",
                    remediation="add poetry.lock or uv.lock for deterministic installs",
                )
            )
    if has_node_manifest and not any(
        (root / x).exists() for x in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")
    ):
        if only is None or "package.json" in only:
            out.append(
                Finding(
                    "dependency_hygiene",
                    "warn",
                    "package.json",
                    1,
                    1,
                    "missing_node_lockfile",
                    "Node manifest found without lockfile",
                    remediation="commit a Node lockfile",
                )
            )

    req = root / "requirements.txt"
    if req.exists() and (only is None or "requirements.txt" in only):
        for i, line in enumerate(
            req.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1
        ):
            out.append(Finding("dependency_hygiene", "warn", "pyproject.toml", 1, 1, "missing_python_lockfile", "Python manifest found without lockfile", remediation="add poetry.lock or uv.lock for deterministic installs"))
    if has_node_manifest and not any((root / x).exists() for x in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")):
        if only is None or "package.json" in only:
            out.append(Finding("dependency_hygiene", "warn", "package.json", 1, 1, "missing_node_lockfile", "Node manifest found without lockfile", remediation="commit a Node lockfile"))

    req = root / "requirements.txt"
    if req.exists() and (only is None or "requirements.txt" in only):
        for i, line in enumerate(req.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if UNPINNED_DEP_RE.match(stripped):
                out.append(
                    Finding(
                        "dependency_hygiene",
                        "warn",
                        "requirements.txt",
                        i,
                        1,
                        "unpinned_dependency",
                        "dependency is not pinned to exact version",
                        remediation="pin with == exact version",
                    )
                )
                out.append(Finding("dependency_hygiene", "warn", "requirements.txt", i, 1, "unpinned_dependency", "dependency is not pinned to exact version", remediation="pin with == exact version"))
    return out


def _load_baseline(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _apply_baseline(findings: list[Finding], baseline: list[dict[str, Any]]) -> list[Finding]:
    if not baseline:
        return findings
    active: list[dict[str, Any]] = []
    today = dt.date.today()
    for item in baseline:
        exp = item.get("expires")
        if isinstance(exp, str):
            try:
                if dt.date.fromisoformat(exp) < today:
                    continue
            except ValueError:
                # Invalid expires format: treat as non-expiring and keep the item active.
                pass
        active.append(item)

    out: list[Finding] = []
    for finding in findings:
        matched = False
        for item in active:
            if item.get("path") and item.get("path") != finding.path:
                continue
            if item.get("check") and item.get("check") != finding.check:
                continue
            if item.get("code") and item.get("code") != finding.code:
                continue
            matched = True
            break
        if not matched:
            out.append(finding)
    return out


def _severity_rank(level: str) -> int:
    return {"info": 0, "warn": 1, "error": 2}.get(level, 2)


def _score(findings: list[Finding]) -> int:
    if not findings:
        return 100
    weights = {"warn": 5, "error": 20}
    penalty = sum(weights.get(f.severity, 20) for f in findings)
    return max(0, 100 - min(100, penalty))


def _report_payload(
    root: Path, findings: list[Finding], *, profile: str, policy_text: str | None
) -> dict[str, Any]:
def _report_payload(root: Path, findings: list[Finding], *, profile: str, policy_text: str | None) -> dict[str, Any]:
    counts = {"info": 0, "warn": 0, "error": 0}
    by_check: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
        by_check[f.check] = by_check.get(f.check, 0) + 1
    policy_hash = hashlib.sha256((policy_text or "").encode("utf-8")).hexdigest()
    return {
        "root": str(root),
        "metadata": {
            "tool": "sdetkit",
            "version": "0.2.8",
            "profile": profile,
            "git_commit": _git_commit_sha(root),
            "generated_at_utc": dt.datetime.now(_UTC).isoformat()
            if profile == "enterprise"
            else "",
            "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat() if profile == "enterprise" else "",  # noqa: UP017
            "policy_hash": policy_hash,
        },
        "summary": {
            "counts": {k: counts[k] for k in sorted(counts)},
            "by_check": {k: by_check[k] for k in sorted(by_check)},
            "findings": len(findings),
            "score": _score(findings),
            "ok": not findings,
        },
        "findings": [f.to_dict() for f in findings],
    }


def _to_sarif(payload: dict[str, Any]) -> dict[str, Any]:
    rules: dict[str, dict[str, str]] = {}
    results: list[dict[str, Any]] = []
    for item in payload["findings"]:
        rid = f"{item['check']}/{item['code']}"
        if rid not in rules:
            rules[rid] = {
                "id": rid,
                "name": item["check"],
                "shortDescription": {"text": item["message"]},
            }
            rules[rid] = {"id": rid, "name": item["check"], "shortDescription": {"text": item["message"]}}
        results.append(
            {
                "ruleId": rid,
                "level": "error" if item["severity"] == "error" else "warning",
                "message": {"text": item["message"]},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": item["path"]},
                            "region": {"startLine": item["line"], "startColumn": item["column"]},
                        }
                    }
                ],
            }
        )
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "sdetkit", "rules": list(rules.values())}},
                "results": results,
            }
        ],
    }


        "runs": [{"tool": {"driver": {"name": "sdetkit", "rules": list(rules.values())}}, "results": results}],
    }




def _generate_sbom(root: Path) -> dict[str, Any]:
    components: list[dict[str, str]] = []
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8", errors="ignore")
        for dep in re.findall(r"[\"\']([A-Za-z0-9_.-]+)(?:[^\"\']*)[\"\']", text):
        for dep in re.findall(r'[\"\']([A-Za-z0-9_.-]+)(?:[^\"\']*)[\"\']', text):
            if dep.lower() in {"project", "dependencies", "name", "x"}:
                continue
            components.append({"type": "library", "name": dep, "purl": f"pkg:pypi/{dep}"})
    package_json = root / "package.json"
    if package_json.exists():
        try:
            pj = json.loads(package_json.read_text(encoding="utf-8"))
        except ValueError:
            pj = {}
        deps = pj.get("dependencies", {})
        if isinstance(deps, dict):
            for name in sorted(deps):
                components.append({"type": "library", "name": name, "purl": f"pkg:npm/{name}"})

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {"component": {"type": "application", "name": root.name}},
        "components": components,
    }


def _render(payload: dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    if fmt == "sarif":
        return json.dumps(_to_sarif(payload), ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    if fmt == "md":
        lines = [
            "# sdetkit repo check report",
            "",
            f"- root: `{payload['root']}`",
            f"- score: {payload['summary']['score']}",
            f"- findings: {payload['summary']['findings']}",
            "",
            "## Findings",
        ]
        for item in payload["findings"]:
            lines.append(
                f"- `{item['severity']}` `{item['check']}` `{item['path']}:{item['line']}:{item['column']}` - {item['message']}"
            )
        return "\n".join(lines) + "\n"

    lines = [
        f"repo: {payload['root']}",
        f"score: {payload['summary']['score']}",
        f"findings: {payload['summary']['findings']}",
    ]
    for item in payload["findings"]:
        lines.append(
            f"[{item['severity']}] {item['path']}:{item['line']}:{item['column']} {item['check']}/{item['code']} {item['message']}"
        )
    return "\n".join(lines) + "\n"


def _needs_fail(findings: list[Finding], fail_on: str | None, min_score: int | None) -> bool:
    if min_score is not None and _score(findings) < min_score:
        return True
    if fail_on is None:
        return bool(findings)
    threshold = _severity_rank(fail_on)
    return any(_severity_rank(f.severity) >= threshold for f in findings)


def _fix_text(text: str, *, eol: str | None) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        eol_part = ""
        content = line
        if line.endswith("\r\n"):
            content = line[:-2]
            eol_part = "\r\n"
        elif line.endswith("\n"):
            content = line[:-1]
            eol_part = "\n"
        elif line.endswith("\r"):
            content = line[:-1]
            eol_part = "\r"
        content = content.rstrip(" \t")
        if eol is None:
            out.append(content + eol_part)
        elif eol == "lf":
            out.append(content + ("\n" if eol_part else ""))
        else:
            out.append(content + ("\r\n" if eol_part else ""))

    fixed = "".join(out)
    if fixed and not fixed.endswith("\n") and not fixed.endswith("\r\n"):
        fixed += "\n" if eol != "crlf" else "\r\n"
    return fixed


def _apply_fixes(root: Path, *, check: bool, dry_run: bool, diff: bool, eol: str | None) -> int:
    changed = 0
    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            original_bytes = path.read_bytes()
            original = original_bytes.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        fixed = _fix_text(original, eol=eol)
        if fixed == original:
            continue

        changed += 1
        if diff or check or dry_run:
            d = difflib.unified_diff(
                original.splitlines(keepends=True),
                fixed.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
            sys.stdout.write("".join(d))

        if not check and not dry_run:
            atomic_write_text(path, fixed)

    if check:
        return 1 if changed else 0
    if dry_run:
        return 0
    return 0


def _resolve_root(user_path: str, *, allow_absolute: bool) -> Path:
    base = Path.cwd().resolve()
    try:
        return safe_path(base, user_path, allow_absolute=allow_absolute)
    except SecurityError:
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit repo")
    sub = parser.add_subparsers(dest="repo_cmd", required=True)

    cp = sub.add_parser("check")
    cp.add_argument("path", nargs="?", default=".")
    cp.add_argument("--format", choices=["text", "json", "md", "sarif"], default="text")
    cp.add_argument("--out", default=None)
    cp.add_argument("--force", action="store_true")
    cp.add_argument("--allow-absolute-path", action="store_true")
    cp.add_argument("--fail-on", choices=["info", "warn", "error"], default=None)
    cp.add_argument("--min-score", type=int, default=None)
    cp.add_argument("--profile", choices=["default", "enterprise"], default="default")
    cp.add_argument("--changed-only", action="store_true")
    cp.add_argument("--diff-base", default="origin/main")
    cp.add_argument("--baseline", default=None)
    cp.add_argument("--policy", default=None)
    cp.add_argument("--sbom-out", default=None)

    fp = sub.add_parser("fix")
    fp.add_argument("path", nargs="?", default=".")
    fp.add_argument("--check", action="store_true")
    fp.add_argument("--dry-run", action="store_true")
    fp.add_argument("--diff", action="store_true")
    fp.add_argument("--eol", choices=["lf", "crlf"], default=None)
    fp.add_argument("--force", action="store_true")
    fp.add_argument("--allow-absolute-path", action="store_true")

    ns = parser.parse_args(argv)

    try:
        root = _resolve_root(ns.path, allow_absolute=bool(ns.allow_absolute_path))
    except SecurityError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if ns.repo_cmd == "check":
        policy_text = None
        if ns.policy:
            try:
                policy_path = safe_path(
                    root, ns.policy, allow_absolute=bool(ns.allow_absolute_path)
                )
                policy_path = safe_path(root, ns.policy, allow_absolute=bool(ns.allow_absolute_path))
                policy_text = policy_path.read_text(encoding="utf-8")
            except (SecurityError, OSError):
                policy_text = None
        baseline_path = None
        if ns.baseline:
            try:
                baseline_path = safe_path(
                    root, ns.baseline, allow_absolute=bool(ns.allow_absolute_path)
                )
                baseline_path = safe_path(root, ns.baseline, allow_absolute=bool(ns.allow_absolute_path))
            except SecurityError:
                baseline_path = None
        findings = run_checks(
            root,
            profile=ns.profile,
            changed_only=bool(ns.changed_only),
            diff_base=str(ns.diff_base),
            baseline=_load_baseline(baseline_path),
        )
        payload = _report_payload(root, findings, profile=ns.profile, policy_text=policy_text)
        rendered = _render(payload, ns.format)
        if ns.sbom_out:
            try:
                sbom_path = safe_path(
                    root, ns.sbom_out, allow_absolute=bool(ns.allow_absolute_path)
                )
                if sbom_path.exists() and not ns.force:
                    print(
                        "refusing to overwrite existing SBOM output (use --force)", file=sys.stderr
                    )
                    return 2
                atomic_write_text(
                    sbom_path,
                    json.dumps(_generate_sbom(root), ensure_ascii=True, sort_keys=True, indent=2)
                    + "\n",
                )
                sbom_path = safe_path(root, ns.sbom_out, allow_absolute=bool(ns.allow_absolute_path))
                if sbom_path.exists() and not ns.force:
                    print("refusing to overwrite existing SBOM output (use --force)", file=sys.stderr)
                    return 2
                atomic_write_text(sbom_path, json.dumps(_generate_sbom(root), ensure_ascii=True, sort_keys=True, indent=2) + "\n")
            except (SecurityError, OSError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 2
        sys.stdout.write(rendered)
        if ns.out:
            try:
                out_path = safe_path(root, ns.out, allow_absolute=bool(ns.allow_absolute_path))
                if out_path.exists() and not ns.force:
                    print("refusing to overwrite existing output (use --force)", file=sys.stderr)
                    return 2
                atomic_write_text(out_path, rendered)
            except (SecurityError, OSError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 2
        return 1 if _needs_fail(findings, ns.fail_on, ns.min_score) else 0

    if ns.check and ns.dry_run:
        print("cannot use --check and --dry-run together", file=sys.stderr)
        return 2
    try:
        return _apply_fixes(
            root,
            check=bool(ns.check),
            dry_run=bool(ns.dry_run),
            diff=bool(ns.diff),
            eol=ns.eol,
        )
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 2
