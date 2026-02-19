from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SEVERITY_RANK = {"info": 1, "warn": 2, "error": 3}
FAIL_ON_TO_SEVERITY = {
    "none": 99,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
    "warn": 2,
    "error": 3,
}
SEVERITY_TO_FAIL_LEVEL = {"info": 1, "warn": 2, "error": 3}
DEFAULT_ALLOWLIST_PATH = Path("tools/security_allowlist.json")
DEFAULT_BASELINE_PATH = Path("tools/security.baseline.json")
INLINE_ALLOW_PREFIX = "# sdetkit: allow-security"

SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "build",
    "site",
    ".mypy_cache",
    ".pytest_cache",
    ".sdetkit",
}
TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
    ".sh",
}
SUSPICIOUS_INPUT_NAMES = {"user_input", "input_path", "filename", "filepath", "path", "name"}
PRINT_ALLOWED_MODULE_SUFFIXES = (
    "/cli.py",
    "/repo.py",
    "/patch.py",
    "/doctor.py",
)


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    path: str
    line: int
    column: int
    message: str
    suggestion: str = ""
    fingerprint: str = ""


@dataclass(frozen=True)
class RuleMeta:
    rule_id: str
    severity: str
    title: str
    description: str


RULES: dict[str, RuleMeta] = {
    "SEC_DANGEROUS_EVAL": RuleMeta(
        "SEC_DANGEROUS_EVAL", "error", "Dangerous code execution", "Use of eval/exec/compile."
    ),
    "SEC_SUBPROCESS_SHELL_TRUE": RuleMeta(
        "SEC_SUBPROCESS_SHELL_TRUE",
        "error",
        "subprocess shell=True",
        "Avoid shell=True in subprocess calls.",
    ),
    "SEC_OS_SYSTEM": RuleMeta(
        "SEC_OS_SYSTEM",
        "error",
        "os.system invocation",
        "Avoid os.system; use subprocess with argument lists.",
    ),
    "SEC_INSECURE_DESERIALIZATION": RuleMeta(
        "SEC_INSECURE_DESERIALIZATION",
        "error",
        "Insecure deserialization",
        "Avoid pickle/dill for untrusted input.",
    ),
    "SEC_YAML_UNSAFE_LOAD": RuleMeta(
        "SEC_YAML_UNSAFE_LOAD",
        "error",
        "Unsafe YAML load",
        "Use yaml.safe_load instead of yaml.load.",
    ),
    "SEC_WEAK_HASH": RuleMeta(
        "SEC_WEAK_HASH",
        "warn",
        "Weak hash usage",
        "Avoid md5/sha1 for security-sensitive workflows.",
    ),
    "SEC_POTENTIAL_PATH_TRAVERSAL": RuleMeta(
        "SEC_POTENTIAL_PATH_TRAVERSAL",
        "warn",
        "Potential path traversal",
        "Use safe_path-style guard for user-controlled path segments.",
    ),
    "SEC_POTENTIAL_UNSAFE_WRITE": RuleMeta(
        "SEC_POTENTIAL_UNSAFE_WRITE",
        "warn",
        "Potential unsafe write",
        "Avoid absolute writes outside workspace allowlist.",
    ),
    "SEC_SECRET_PATTERN": RuleMeta(
        "SEC_SECRET_PATTERN",
        "error",
        "Secret-like pattern",
        "Potential credential or private key material detected.",
    ),
    "SEC_HIGH_ENTROPY_STRING": RuleMeta(
        "SEC_HIGH_ENTROPY_STRING",
        "warn",
        "High entropy string",
        "Potential token-like hardcoded value detected.",
    ),
    "SEC_NETWORK_TIMEOUT": RuleMeta(
        "SEC_NETWORK_TIMEOUT",
        "warn",
        "Network call missing timeout",
        "Set explicit timeout for requests/urllib calls.",
    ),
    "SEC_DEBUG_PRINT": RuleMeta(
        "SEC_DEBUG_PRINT", "info", "Debug print in src", "Avoid print() in src/ modules."
    ),
    "SEC_DEP_VULN": RuleMeta(
        "SEC_DEP_VULN",
        "error",
        "Dependency vulnerability",
        "Dependency version matches local vulnerability rule.",
    ),
}

OFFLINE_VULN_RULES: dict[str, dict[str, str]] = {
    "pyyaml": {
        "5.3": "CVE-2020-14343: unsafe loader behavior in older versions.",
        "5.4": "CVE-2020-14343: unsafe loader behavior in older versions.",
    },
    "jinja2": {
        "2.10": "CVE-2019-10906: sandbox escape in older versions.",
    },
}

SECRET_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("SEC_SECRET_PATTERN", re.compile(r"AKIA[0-9A-Z]{16}"), "Potential AWS access key"),
    ("SEC_SECRET_PATTERN", re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"), "Potential GitHub token"),
    (
        "SEC_SECRET_PATTERN",
        re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{8,}"),
        "Potential hardcoded API key",
    ),
    (
        "SEC_SECRET_PATTERN",
        re.compile(r"(?i)(token|secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{8,}"),
        "Potential hardcoded credential",
    ),
    (
        "SEC_SECRET_PATTERN",
        re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) KEY-----"),
        "Potential PEM private key",
    ),
]


class SecurityScanError(ValueError):
    pass


class _RuleVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: str, lines: list[str]) -> None:
        self.rel_path = rel_path
        self.lines = lines
        self.findings: list[Finding] = []

    def _add(self, rule_id: str, node: ast.AST, message: str, suggestion: str = "") -> None:
        self.findings.append(
            Finding(
                rule_id=rule_id,
                severity=RULES[rule_id].severity,
                path=self.rel_path,
                line=getattr(node, "lineno", 1),
                column=getattr(node, "col_offset", 0),
                message=message,
                suggestion=suggestion,
            )
        )

    def _allow_print_for_module(self) -> bool:
        rel = self.rel_path.replace("\\", "/")
        return rel.startswith("src/sdetkit/") and rel.endswith(PRINT_ALLOWED_MODULE_SUFFIXES)

    def visit_Call(self, node: ast.Call) -> Any:
        name = _call_name(node)
        if name in {"eval", "exec"}:
            self._add(
                "SEC_DANGEROUS_EVAL", node, f"Avoid {name}(); dynamic execution is dangerous."
            )
        if name == "os.system":
            self._add(
                "SEC_OS_SYSTEM", node, "os.system detected; use subprocess with argument list."
            )
        if name and name.startswith("subprocess.") and _kw_bool(node, "shell", True):
            self._add(
                "SEC_SUBPROCESS_SHELL_TRUE",
                node,
                "subprocess call uses shell=True.",
                suggestion="Set shell=False and pass command as a list.",
            )
        if name in {"pickle.load", "pickle.loads"} or name.startswith("dill"):
            self._add(
                "SEC_INSECURE_DESERIALIZATION",
                node,
                f"Insecure deserialization via {name}.",
            )
        if name == "yaml.load" and not _is_safe_yaml_loader(node):
            self._add(
                "SEC_YAML_UNSAFE_LOAD",
                node,
                "yaml.load used without SafeLoader/safe_load.",
                suggestion="Replace with yaml.safe_load(...).",
            )
        if name in {"hashlib.md5", "hashlib.sha1", "md5", "sha1"}:
            self._add("SEC_WEAK_HASH", node, f"Weak hash usage: {name}.")
        if (
            name
            and name.startswith("requests.")
            and name.split(".")[-1]
            in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "head",
                "request",
            }
        ):
            if not _has_kw(node, "timeout"):
                self._add(
                    "SEC_NETWORK_TIMEOUT",
                    node,
                    f"{name} without timeout.",
                    suggestion="Add timeout=<seconds> argument.",
                )
        if name in {"urllib.request.urlopen", "urlopen"} and not _has_kw(node, "timeout"):
            self._add(
                "SEC_NETWORK_TIMEOUT",
                node,
                "urllib.request.urlopen without timeout.",
                suggestion="Add timeout=<seconds> argument.",
            )
        if name in {
            "os.path.join",
            "pathlib.Path",
            "Path",
            "pathlib.Path.joinpath",
            "Path.joinpath",
        }:
            if _looks_untrusted_path_args(node):
                self._add(
                    "SEC_POTENTIAL_PATH_TRAVERSAL",
                    node,
                    "Path join with potentially user-controlled segment.",
                    suggestion="Validate with safe_path before filesystem access.",
                )
        if name == "open" and _is_write_mode_open(node):
            if _is_absolute_literal(node):
                self._add(
                    "SEC_POTENTIAL_UNSAFE_WRITE",
                    node,
                    "Write to absolute path detected.",
                    suggestion="Restrict writes to workspace or explicit allowlist.",
                )
        if (
            self.rel_path.startswith("src/")
            and name == "print"
            and not self._allow_print_for_module()
        ):
            self._add("SEC_DEBUG_PRINT", node, "print(...) found in src/.")
        self.generic_visit(node)


def _call_name(node: ast.Call) -> str:
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        parts = [fn.attr]
        value = fn.value
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            parts.append(value.id)
        return ".".join(reversed(parts))
    return ""


def _kw_bool(node: ast.Call, key: str, expected: bool) -> bool:
    for kw in node.keywords:
        if (
            kw.arg == key
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, bool)
        ):
            return kw.value.value is expected
    return False


def _has_kw(node: ast.Call, key: str) -> bool:
    return any(kw.arg == key for kw in node.keywords)


def _looks_untrusted_path_args(node: ast.Call) -> bool:
    for arg in node.args:
        if isinstance(arg, ast.Name) and arg.id.lower() in SUSPICIOUS_INPUT_NAMES:
            return True
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and ".." in arg.value:
            return True
    return False


def _is_write_mode_open(node: ast.Call) -> bool:
    if (
        len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and isinstance(node.args[1].value, str)
    ):
        mode = node.args[1].value
        return any(ch in mode for ch in ("w", "a", "x"))
    for kw in node.keywords:
        if (
            kw.arg == "mode"
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, str)
        ):
            return any(ch in kw.value.value for ch in ("w", "a", "x"))
    return False


def _is_absolute_literal(node: ast.Call) -> bool:
    if not node.args:
        return False
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value.startswith("/")
    return False


def _is_safe_yaml_loader(node: ast.Call) -> bool:
    for kw in node.keywords:
        if kw.arg != "Loader":
            continue
        if isinstance(kw.value, ast.Attribute) and kw.value.attr in {"SafeLoader", "CSafeLoader"}:
            return True
        if isinstance(kw.value, ast.Name) and kw.value.id in {"SafeLoader", "CSafeLoader"}:
            return True
    return False


def _should_scan_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    return path.name in {".env", ".env.local", ".env.production"}


def _iter_files(root: Path) -> list[Path]:
    resolved_root = root.resolve(strict=True)
    files: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            resolved = p.resolve(strict=False)
        except OSError:
            continue
        if resolved != resolved_root and resolved_root not in resolved.parents:
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if not _should_scan_file(p):
            continue
        try:
            if p.stat().st_size > 1_000_000:
                continue
        except OSError:
            continue
        files.append(p)
    files.sort(key=lambda x: x.as_posix())
    return files


def _normalized_message(message: str) -> str:
    return re.sub(r"\s+", " ", message.strip()).lower()


def _fingerprint(rule_id: str, path: str, line: int, message: str) -> str:
    raw = f"{rule_id}|{path}|{line}|{_normalized_message(message)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _load_repo_allowlist(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SecurityScanError(f"invalid allowlist JSON: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("entries", []), list):
        raise SecurityScanError("allowlist file must be object with 'entries' list")
    entries = [item for item in payload["entries"] if isinstance(item, dict)]
    entries.sort(
        key=lambda x: (
            str(x.get("rule_id", "")),
            str(x.get("path", "")),
            int(x.get("line", 0) or 0),
        )
    )
    return entries


def _inline_allowed(lines: list[str], finding: Finding) -> bool:
    line_no = finding.line
    for idx in (line_no - 1, line_no - 2):
        if idx < 0 or idx >= len(lines):
            continue
        txt = lines[idx]
        if INLINE_ALLOW_PREFIX in txt:
            allow_rule = txt.split(INLINE_ALLOW_PREFIX, 1)[1].strip()
            if allow_rule == finding.rule_id:
                return True
    return False


def _repo_allowed(entries: list[dict[str, Any]], finding: Finding) -> bool:
    for item in entries:
        if str(item.get("rule_id", "")) != finding.rule_id:
            continue
        if str(item.get("path", "")) != finding.path:
            continue
        line = item.get("line")
        if isinstance(line, int) and line != finding.line:
            continue
        fp = item.get("fingerprint")
        if isinstance(fp, str) and fp and fp != finding.fingerprint:
            continue
        return True
    return False


def _is_test_fixture_secret(rel_path: str, line: str) -> bool:
    if not rel_path.startswith("tests/"):
        return False
    marker_tokens = {"TOPSECRET", "SHOULD_NOT_LEAK", "dummy", "example"}
    upper_line = line.upper()
    return any(token in upper_line for token in marker_tokens)


def _scan_text_patterns(rel_path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()
    for i, line in enumerate(lines, start=1):
        for rule_id, pattern, msg in SECRET_PATTERNS:
            if pattern.search(line):
                if _is_test_fixture_secret(rel_path, line):
                    continue
                findings.append(
                    Finding(
                        rule_id=rule_id,
                        severity=RULES[rule_id].severity,
                        path=rel_path,
                        line=i,
                        column=0,
                        message=msg,
                    )
                )
        # quoted token-like strings
        for match in re.finditer(r"['\"]([A-Za-z0-9+/=_\-]{20,})['\"]", line):
            token = match.group(1)
            if _entropy(token) >= 4.0 and not token.isdigit():
                findings.append(
                    Finding(
                        rule_id="SEC_HIGH_ENTROPY_STRING",
                        severity=RULES["SEC_HIGH_ENTROPY_STRING"].severity,
                        path=rel_path,
                        line=i,
                        column=match.start(1),
                        message="High-entropy string literal detected.",
                    )
                )
    return findings


def _entropy(text: str) -> float:
    if not text:
        return 0.0
    counts: dict[str, int] = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    total = len(text)
    return -sum((v / total) * math.log2(v / total) for v in counts.values())


def scan_repo(root: Path, *, allowlist_path: Path | None = None) -> list[Finding]:
    allow_entries = _load_repo_allowlist(allowlist_path or DEFAULT_ALLOWLIST_PATH)
    findings: list[Finding] = []
    for file_path in _iter_files(root):
        rel = file_path.relative_to(root).as_posix()
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lines = text.splitlines()
        file_findings: list[Finding] = []
        if file_path.suffix == ".py":
            try:
                tree = ast.parse(text)
            except SyntaxError:
                tree = None
            if tree is not None:
                visitor = _RuleVisitor(rel, lines)
                visitor.visit(tree)
                file_findings.extend(visitor.findings)
        file_findings.extend(_scan_text_patterns(rel, text))

        for finding in file_findings:
            with_fp = Finding(
                **{
                    **asdict(finding),
                    "fingerprint": _fingerprint(
                        finding.rule_id, finding.path, finding.line, finding.message
                    ),
                }
            )
            if _inline_allowed(lines, with_fp):
                continue
            if _repo_allowed(allow_entries, with_fp):
                continue
            file_line = lines[with_fp.line - 1] if 0 < with_fp.line <= len(lines) else ""
            if with_fp.rule_id == "SEC_WEAK_HASH" and INLINE_ALLOW_PREFIX in file_line:
                continue
            findings.append(with_fp)

    findings.sort(key=lambda x: (x.path, x.line, x.column, x.rule_id, x.message))
    return findings


def _parse_pinned_dependencies(path: Path) -> list[tuple[str, str, int]]:
    deps: list[tuple[str, str, int]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"([A-Za-z0-9_.\-]+)==([A-Za-z0-9_.\-]+)", line)
        if not m:
            continue
        deps.append((m.group(1).lower().replace("_", "-"), m.group(2), line_no))
    deps.sort()
    return deps


def _scan_dependency_vulns_offline(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for rel in ("requirements.lock", "requirements.txt.lock", "requirements.txt"):
        path = root / rel
        if not path.exists() or not path.is_file():
            continue
        for name, version, line_no in _parse_pinned_dependencies(path):
            advisories = OFFLINE_VULN_RULES.get(name, {})
            for vulnerable_prefix, reason in sorted(advisories.items()):
                if version.startswith(vulnerable_prefix):
                    findings.append(
                        Finding(
                            rule_id="SEC_DEP_VULN",
                            severity="error",
                            path=rel,
                            line=line_no,
                            column=1,
                            message=f"{name}=={version} matches offline vulnerability rule ({reason})",
                            suggestion="Upgrade to a patched dependency version.",
                            fingerprint=_fingerprint(
                                "SEC_DEP_VULN", rel, line_no, f"{name}=={version}|{reason}"
                            ),
                        )
                    )
    findings.sort(key=lambda x: (x.path, x.line, x.rule_id, x.message))
    return findings


def _generate_sbom_cyclonedx(root: Path) -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for rel in ("requirements.lock", "requirements.txt.lock", "requirements.txt"):
        path = root / rel
        if not path.exists() or not path.is_file():
            continue
        for name, version, _ in _parse_pinned_dependencies(path):
            key = (name, version)
            if key in seen:
                continue
            seen.add(key)
            components.append(
                {
                    "bom-ref": f"pkg:pypi/{name}@{version}",
                    "type": "library",
                    "name": name,
                    "version": version,
                    "purl": f"pkg:pypi/{name}@{version}",
                }
            )
    components.sort(key=lambda x: (str(x["name"]), str(x["version"])))
    serial = hashlib.sha256(root.as_posix().encode("utf-8")).hexdigest()
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "serialNumber": f"urn:uuid:{serial[:8]}-{serial[8:12]}-{serial[12:16]}-{serial[16:20]}-{serial[20:32]}",
        "metadata": {"component": {"name": root.name or "repository", "type": "application"}},
        "components": components,
    }


def _maybe_online_dep_scan(root: Path) -> list[Finding]:
    cmd = os.environ.get("SDETKIT_SECURITY_ONLINE_CMD", "")
    if not cmd.strip():
        return []
    proc = subprocess.run(shlex.split(cmd), cwd=str(root), capture_output=True, text=True)
    if proc.returncode != 0:
        raise SecurityScanError(
            "online dependency scan command failed; provide a working command in "
            "SDETKIT_SECURITY_ONLINE_CMD or run without --online"
        )
    return []


def run_security_scan(
    root: Path,
    *,
    allowlist_path: Path,
    online: bool,
    sbom_output: Path | None,
) -> tuple[list[Finding], dict[str, Any]]:
    findings = scan_repo(root, allowlist_path=allowlist_path)
    findings.extend(_scan_dependency_vulns_offline(root))
    if online:
        findings.extend(_maybe_online_dep_scan(root))
    findings.sort(key=lambda x: (x.path, x.line, x.column, x.rule_id, x.message))
    sbom = _generate_sbom_cyclonedx(root)
    if sbom_output is not None:
        sbom_output.parent.mkdir(parents=True, exist_ok=True)
        sbom_output.write_text(
            json.dumps(sbom, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
    return findings, sbom


def _to_json_payload(
    findings: list[Finding],
    *,
    new_only: list[Finding] | None = None,
    sbom: dict[str, Any] | None = None,
) -> dict[str, Any]:
    counts = {"info": 0, "warn": 0, "error": 0}
    for f in findings:
        counts[f.severity] += 1
    payload = {
        "version": 1,
        "counts": counts,
        "findings": [asdict(x) for x in findings],
        "new_findings": [asdict(x) for x in findings]
        if new_only is None
        else [asdict(x) for x in new_only],
    }
    if sbom is not None:
        payload["sbom"] = sbom
    return payload


def _to_text(findings: list[Finding], *, sbom_components: int = 0) -> str:
    counts = {"info": 0, "warn": 0, "error": 0}
    for f in findings:
        counts[f.severity] += 1
    lines = [
        f"security scan: total={len(findings)} error={counts['error']} warn={counts['warn']} info={counts['info']}",
        f"sbom components: {sbom_components}",
        "top findings:",
    ]
    for item in findings[:15]:
        lines.append(f"- [{item.severity}] {item.rule_id} {item.path}:{item.line} {item.message}")
    if not findings:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _to_sarif(findings: list[Finding]) -> dict[str, Any]:
    rules = []
    for rid in sorted({f.rule_id for f in findings}):
        meta = RULES[rid]
        rules.append(
            {
                "id": rid,
                "name": meta.title,
                "shortDescription": {"text": meta.title},
                "fullDescription": {"text": meta.description},
                "help": {
                    "text": f"{meta.description} Fix guidance: review the finding and apply the suggested remediation."
                },
                "defaultConfiguration": {
                    "level": {"info": "note", "warn": "warning", "error": "error"}[meta.severity]
                },
            }
        )
    results = []
    for f in findings:
        results.append(
            {
                "ruleId": f.rule_id,
                "level": {"info": "note", "warn": "warning", "error": "error"}[f.severity],
                "message": {"text": f.message},
                "fingerprints": {"primaryLocationLineHash": f.fingerprint},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": f.path},
                            "region": {"startLine": f.line, "startColumn": max(f.column, 1)},
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
                "tool": {"driver": {"name": "sdetkit-security-gate", "rules": rules}},
                "results": results,
            }
        ],
    }


def _write_output(text: str, output: str | None) -> None:
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _severity_trips(findings: list[Finding], threshold: str) -> bool:
    if threshold == "none":
        return False
    gate = FAIL_ON_TO_SEVERITY[threshold]
    return any(SEVERITY_TO_FAIL_LEVEL[f.severity] >= gate for f in findings)


def _load_baseline(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise SecurityScanError("baseline must be JSON object containing entries[]")
    entries = [x for x in data["entries"] if isinstance(x, dict)]
    entries.sort(
        key=lambda x: (
            str(x.get("path", "")),
            str(x.get("rule_id", "")),
            str(x.get("fingerprint", "")),
        )
    )
    return entries


def _make_baseline_entries(findings: list[Finding]) -> list[dict[str, Any]]:
    entries = [
        {
            "rule_id": f.rule_id,
            "severity": f.severity,
            "path": f.path,
            "line": f.line,
            "fingerprint": f.fingerprint,
            "message": _normalized_message(f.message)[:120],
        }
        for f in findings
    ]
    entries.sort(key=lambda x: (x["path"], x["rule_id"], x["line"], x["fingerprint"]))
    return entries


def _filter_new(findings: list[Finding], baseline_entries: list[dict[str, Any]]) -> list[Finding]:
    known = {
        (
            str(x.get("rule_id", "")),
            str(x.get("path", "")),
            int(x.get("line", 0) or 0),
            str(x.get("fingerprint", "")),
        )
        for x in baseline_entries
    }
    return [f for f in findings if (f.rule_id, f.path, f.line, f.fingerprint) not in known]


def _render(
    findings: list[Finding],
    fmt: str,
    *,
    new_only: list[Finding] | None = None,
    sbom: dict[str, Any] | None = None,
) -> str:
    if fmt == "text":
        target = findings if new_only is None else new_only
        components = len(sbom.get("components", [])) if isinstance(sbom, dict) else 0
        return _to_text(target, sbom_components=components)
    if fmt == "json":
        return (
            json.dumps(
                _to_json_payload(findings, new_only=new_only, sbom=sbom),
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
    if fmt == "sarif":
        target = findings if new_only is None else new_only
        return json.dumps(_to_sarif(target), ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    raise SecurityScanError(f"unsupported format: {fmt}")


def _fix_yaml_safe_load(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    out = re.sub(r"\byaml\.load\s*\(", "yaml.safe_load(", text)
    if out != text:
        path.write_text(out, encoding="utf-8")
        return True
    return False


def _inject_requests_timeout(text: str, timeout: int) -> str:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if "requests." not in line or "timeout=" in line:
            continue
        m = re.search(r"requests\.(get|post|put|patch|delete|head|request)\((.*)\)", line)
        if not m:
            continue
        lines[idx] = line[:-1] + f", timeout={timeout})"
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def _fix_requests_timeout(path: Path, timeout: int) -> bool:
    text = path.read_text(encoding="utf-8")
    out = _inject_requests_timeout(text, timeout)
    if out != text:
        path.write_text(out, encoding="utf-8")
        return True
    return False


def _run_ruff_fix(root: Path) -> tuple[bool, str]:
    if not shutil.which("ruff"):
        return False, "ruff not available; skipped"
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", str(root), "--fix"], capture_output=True, text=True
    )
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit security")
    sub = parser.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=".")
    common.add_argument("--allowlist", default=str(DEFAULT_ALLOWLIST_PATH))
    common.add_argument("--format", choices=["text", "json", "sarif"], default="text")
    common.add_argument("--output", default=None)
    common.add_argument(
        "--fail-on",
        choices=["none", "low", "medium", "high", "critical", "warn", "error"],
        default="medium",
    )
    common.add_argument("--online", action="store_true", help="Enable optional online scanning")
    common.add_argument("--sbom-output", default=None, help="Write CycloneDX SBOM JSON to file")

    sub.add_parser("scan", parents=[common])
    sub.add_parser("report", parents=[common])

    chk = sub.add_parser("check", parents=[common])
    chk.add_argument("--baseline", default=str(DEFAULT_BASELINE_PATH))

    sub.add_parser("baseline", parents=[common])

    fixp = sub.add_parser("fix")
    fixp.add_argument("--root", default=".")
    fixp.add_argument("--allowlist", default=str(DEFAULT_ALLOWLIST_PATH))
    fixp.add_argument("--timeout", type=int, default=10)
    fixp.add_argument("--dry-run", action="store_true", default=True)
    fixp.add_argument("--apply", action="store_true")
    fixp.add_argument("--run-ruff", action="store_true")

    ns = parser.parse_args(argv)
    try:
        root = Path(ns.root).resolve()
        allowlist = Path(ns.allowlist)
        findings: list[Finding] = []
        sbom: dict[str, Any] | None = None

        if ns.cmd == "baseline":
            findings, _ = run_security_scan(
                root,
                allowlist_path=allowlist,
                online=bool(getattr(ns, "online", False)),
                sbom_output=None,
            )
            entries = _make_baseline_entries(findings)
            baseline_payload = {"version": 1, "entries": entries}
            if not ns.output:
                raise SecurityScanError("baseline requires --output <path>")
            output = Path(ns.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(baseline_payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            sys.stdout.write(f"baseline written: {output.as_posix()} ({len(entries)} entries)\n")
            return 0

        if ns.cmd == "fix":
            changed = 0
            previews: list[str] = []
            should_apply = bool(ns.apply)
            for py_file in [p for p in _iter_files(root) if p.suffix == ".py"]:
                before = py_file.read_text(encoding="utf-8")
                did_change = _fix_yaml_safe_load(py_file) if should_apply else False
                did_change = (
                    _fix_requests_timeout(py_file, ns.timeout) if should_apply else False
                ) or did_change
                if not should_apply:
                    candidate = re.sub(r"\byaml\.load\s*\(", "yaml.safe_load(", before)
                    candidate = _inject_requests_timeout(candidate, ns.timeout)
                    if candidate != before:
                        rel = py_file.relative_to(root).as_posix()
                        previews.append(
                            "\n".join(
                                difflib.unified_diff(
                                    before.splitlines(),
                                    candidate.splitlines(),
                                    fromfile=f"a/{rel}",
                                    tofile=f"b/{rel}",
                                    lineterm="",
                                )
                            )
                        )
                        changed += 1
                if did_change:
                    changed += 1
            if ns.run_ruff:
                ok, msg = _run_ruff_fix(root)
                status = "ruff-fix applied" if ok else "ruff-fix had issues"
                sys.stdout.write(f"{status}: {msg}\n")
            if should_apply:
                sys.stdout.write(f"security fix complete; files changed: {changed}\n")
            else:
                sys.stdout.write("security fix dry-run (safe deterministic fixes only)\n")
                if previews:
                    sys.stdout.write("\n".join(previews[:5]) + "\n")
                sys.stdout.write(
                    "notes: risky transforms are not auto-applied; use manual remediation for complex subprocess/eval patterns.\n"
                )
                sys.stdout.write(f"security fix complete; candidate files: {changed}\n")
            return 0

        sbom_output = Path(ns.sbom_output) if getattr(ns, "sbom_output", None) else None
        findings, sbom = run_security_scan(
            root,
            allowlist_path=allowlist,
            online=bool(getattr(ns, "online", False)),
            sbom_output=sbom_output,
        )

        if ns.cmd == "check":
            baseline_path = Path(ns.baseline)
            if baseline_path.exists():
                baseline_entries = _load_baseline(baseline_path)
                new_findings = _filter_new(findings, baseline_entries)
            else:
                new_findings = findings
            rendered = _render(findings, ns.format, new_only=new_findings, sbom=sbom)
            _write_output(rendered, ns.output)
            return 1 if _severity_trips(new_findings, ns.fail_on) else 0

        if ns.cmd == "report":
            rendered = _render(findings, ns.format, sbom=sbom)
            _write_output(rendered, ns.output)
            return 0

        rendered = _render(findings, ns.format, sbom=sbom)
        _write_output(rendered, ns.output)
        return 1 if _severity_trips(findings, ns.fail_on) else 0
    except SecurityScanError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2
    except OSError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
