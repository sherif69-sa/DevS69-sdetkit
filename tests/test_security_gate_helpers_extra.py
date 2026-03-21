from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import sdetkit.security_gate as sg


def _call(expr: str):
    node = ast.parse(expr).body[0]
    assert isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    return node.value


def test_ast_helper_detectors() -> None:
    c1 = _call("open('/tmp/x', 'w')")
    assert sg._call_name(c1) == "open"
    assert sg._is_write_mode_open(c1)
    assert sg._is_absolute_literal(c1)

    c2 = _call("yaml.load(data, Loader=yaml.SafeLoader)")
    assert sg._is_safe_yaml_loader(c2)

    c3 = _call("requests.get(url)")
    assert sg._looks_untrusted_path_args(c3) is False


def test_misc_helper_functions() -> None:
    assert sg._looks_like_slug("very-long-token-with-many-segments")
    assert sg._looks_like_uuid("123e4567-e89b-12d3-a456-426614174000")
    assert sg._looks_like_hex_digest("a" * 64)
    assert sg._looks_like_path("src/app.py")
    assert sg._normalized_message("  hi  ") == "hi"
    fp = sg._fingerprint("R", "p", 1, "m")
    assert isinstance(fp, str) and fp


def test_security_gate_helper_paths_and_rendering(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("print('x')\n", encoding="utf-8")
    (src / "b.bin").write_bytes(b"\xff\xfe")
    (src / ".git").mkdir()
    (src / ".git" / "x.py").write_text("print(1)\n", encoding="utf-8")

    files = sg._iter_files(src)
    rels = [f.relative_to(src).as_posix() for f in files]
    assert "a.py" in rels
    assert ".git/x.py" not in rels
    assert sg._should_scan_file(src / "a.py") is True
    assert sg._should_scan_file(src / "b.bin") is False

    allow = tmp_path / "allow.json"
    allow.write_text(
        '{"entries":[{"rule_id":"SEC_OS_SYSTEM","path":"src/a.py","line":1}]}\n', encoding="utf-8"
    )
    entries = sg._load_repo_allowlist(allow)
    finding = sg.Finding("SEC_OS_SYSTEM", "error", "src/a.py", 1, 1, "m")
    assert sg._repo_allowed(entries, finding) is True
    assert sg._inline_allowed(["# sdetkit: allow-security SEC_OS_SYSTEM"], finding) is True

    allow.write_text('{"bad":1}\n', encoding="utf-8")
    with pytest.raises(KeyError):
        sg._load_repo_allowlist(allow)

    secret_line = "api_" + "key=ABCDEFGH\n"
    findings = sg._scan_text_patterns("src/a.py", secret_line)
    assert any(x.rule_id == "SEC_SECRET_PATTERN" for x in findings)

    payload = sg._to_json_payload(findings)
    assert "findings" in payload and "counts" in payload
    assert "findings:" in sg._to_text(findings, sbom_components=2).lower()
    sarif = sg._to_sarif(findings)
    assert sarif["runs"][0]["tool"]["driver"]["name"] == "sdetkit-security-gate"

    assert sg._severity_trips(findings, "warn") is True
    assert sg._severity_trips([], "error") is False

    budgets = sg._parse_rule_budgets(["SEC_OS_SYSTEM=1", "SEC_WEAK_HASH=2"])
    assert budgets["SEC_OS_SYSTEM"] == 1
    with pytest.raises(sg.SecurityScanError):
        sg._parse_rule_budgets(["badbudget"])

    budget_payload, ok = sg._enforce_budgets(
        [finding],
        max_total=None,
        max_info=None,
        max_warn=None,
        max_error=None,
        rule_budgets={"SEC_OS_SYSTEM": 0},
    )
    assert ok is False
    assert budget_payload["rule_limits"]["SEC_OS_SYSTEM"] == 0
    assert budget_payload["exceeded_rules"][0]["count"] == 1

    base_entries = sg._make_baseline_entries([finding])
    assert base_entries and base_entries[0]["rule_id"] == "SEC_OS_SYSTEM"
    assert sg._filter_new([finding], base_entries) == []

    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"entries": base_entries}), encoding="utf-8")
    assert sg._load_baseline(baseline_path) == base_entries

    scan_path = tmp_path / "scan.json"
    scan_payload = {
        "findings": [
            {
                "rule_id": "SEC_OS_SYSTEM",
                "severity": "error",
                "path": "x.py",
                "line": "1",
                "column": "2",
                "message": "m",
                "suggestion": "s",
                "fingerprint": "fp",
            },
            {"rule_id": "BAD", "severity": "x"},
        ],
        "sbom": {"components": []},
    }
    scan_path.write_text(json.dumps(scan_payload), encoding="utf-8")
    loaded, sbom = sg._load_scan_json(scan_path)
    assert len(loaded) == 1
    assert sbom == {"components": []}

    rendered = sg._render(loaded, "json", new_only=[], sbom=sbom)
    assert '"new_findings"' in rendered
    assert "sbom components" in sg._render(loaded, "text", new_only=loaded, sbom=sbom).lower()


def test_inject_requests_timeout_skips_invalid_ast_offsets(monkeypatch: pytest.MonkeyPatch) -> None:
    text = "requests.get(url)\n"
    tree = ast.parse(text)
    call = next(node for node in ast.walk(tree) if isinstance(node, ast.Call))
    call.end_col_offset = -1

    monkeypatch.setattr(sg.ast, "parse", lambda _text: tree)

    injected = sg._inject_requests_timeout(text, 9)
    assert injected == text


def test_security_gate_fix_and_dep_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    req = tmp_path / "requirements.txt"
    req.write_text("filelock==3.18.0\npyyaml==5.4\n", encoding="utf-8")

    parsed = sg._parse_pinned_dependencies(req)
    assert ("filelock", "3.18.0", 1) in parsed
    vulns = sg._scan_dependency_vulns_offline(tmp_path)
    assert vulns and all(v.rule_id == "SEC_DEP_VULN" for v in vulns)

    sbom = sg._generate_sbom_cyclonedx(tmp_path)
    assert sbom["bomFormat"] == "CycloneDX"

    py = tmp_path / "x.py"
    py.write_text("import yaml\na = yaml.load(x)\n", encoding="utf-8")
    assert sg._fix_yaml_safe_load(py) is True
    assert "safe_load" in py.read_text(encoding="utf-8")

    injected = sg._inject_requests_timeout("requests.get(url)\nrequests.post(url, timeout=1)\n", 7)
    assert "requests.get(url, timeout=7)" in injected

    py2 = tmp_path / "y.py"
    py2.write_text("import requests\nrequests.get(url)\n", encoding="utf-8")
    assert sg._fix_requests_timeout(py2, 5) is True
    assert "timeout=5" in py2.read_text(encoding="utf-8")

    monkeypatch.setattr(sg.shutil, "which", lambda _x: None)
    ok, msg = sg._run_ruff_fix(tmp_path)
    assert ok is False
    assert "not available" in msg
