from __future__ import annotations

import json
import os
from pathlib import Path

from sdetkit import cli


def _run(args: list[str]) -> int:
    return cli.main(["security", *args])


def test_security_scan_detects_multiple_rules(tmp_path: Path, capsys) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text(
        """
import hashlib
import os
import pickle
import requests
import yaml

print('debug')
os.system('echo bad')
value = eval('1+1')
obj = pickle.loads(data)
cfg = yaml.load(doc)
h = hashlib.md5(b'x').hexdigest()
resp = requests.get('https://example.com')
""".strip()
        + "\n",
        encoding="utf-8",
    )

    rc = _run(["scan", "--root", str(tmp_path), "--format", "json", "--fail-on", "none"])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    rules = {item["rule_id"] for item in payload["findings"]}
    assert {
        "SEC_DEBUG_PRINT",
        "SEC_OS_SYSTEM",
        "SEC_DANGEROUS_EVAL",
        "SEC_INSECURE_DESERIALIZATION",
        "SEC_YAML_UNSAFE_LOAD",
        "SEC_WEAK_HASH",
        "SEC_NETWORK_TIMEOUT",
    }.issubset(rules)


def test_security_baseline_regression_only(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    file = src / "mod.py"
    file.write_text("import os\nos.system('echo x')\n", encoding="utf-8")

    baseline = tmp_path / "baseline.json"
    assert _run(["baseline", "--root", str(tmp_path), "--output", str(baseline)]) == 0

    # Existing finding should not fail with baseline
    assert (
        _run(["check", "--root", str(tmp_path), "--baseline", str(baseline), "--format", "json"])
        == 0
    )

    # New finding should fail regression gate
    file.write_text(
        "import os\nimport requests\nos.system('echo x')\nrequests.get('https://example.com')\n",
        encoding="utf-8",
    )
    assert (
        _run(["check", "--root", str(tmp_path), "--baseline", str(baseline), "--format", "json"])
        == 1
    )


def test_security_scan_output_is_deterministic(tmp_path: Path, capsys) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "z.py").write_text("import os\nos.system('z')\n", encoding="utf-8")
    (src / "a.py").write_text("import os\nos.system('a')\n", encoding="utf-8")

    assert _run(["scan", "--root", str(tmp_path), "--format", "json", "--fail-on", "none"]) == 0
    first = capsys.readouterr().out
    assert _run(["scan", "--root", str(tmp_path), "--format", "json", "--fail-on", "none"]) == 0
    second = capsys.readouterr().out
    assert first == second


def test_security_sarif_shape(tmp_path: Path, capsys) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("import os\nos.system('x')\n", encoding="utf-8")

    rc = _run(["scan", "--root", str(tmp_path), "--format", "sarif", "--fail-on", "none"])
    assert rc == 0
    sarif = json.loads(capsys.readouterr().out)
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "sdetkit-security-gate"
    assert run["tool"]["driver"]["rules"]
    assert run["results"][0]["ruleId"]
    assert run["results"][0]["locations"]


def test_security_check_json_reports_empty_new_findings_when_baseline_matches(
    tmp_path: Path, capsys
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    target = src / "mod.py"
    target.write_text("import os\nos.system('echo x')\n", encoding="utf-8")

    baseline = tmp_path / "baseline.json"
    assert _run(["baseline", "--root", str(tmp_path), "--output", str(baseline)]) == 0
    capsys.readouterr()

    assert (
        _run(["check", "--root", str(tmp_path), "--baseline", str(baseline), "--format", "json"])
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["findings"]
    assert payload["new_findings"] == []


def test_security_check_json_reports_only_regressions_in_new_findings(
    tmp_path: Path, capsys
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    target = src / "mod.py"
    target.write_text(
        "import os\nimport requests\nos.system('echo x')\n",
        encoding="utf-8",
    )

    baseline = tmp_path / "baseline.json"
    assert _run(["baseline", "--root", str(tmp_path), "--output", str(baseline)]) == 0
    capsys.readouterr()

    target.write_text(
        "import os\nimport requests\nos.system('echo x')\nrequests.get('https://example.com')\n",
        encoding="utf-8",
    )
    assert (
        _run(["check", "--root", str(tmp_path), "--baseline", str(baseline), "--format", "json"])
        == 1
    )
    payload = json.loads(capsys.readouterr().out)
    all_rules = {item["rule_id"] for item in payload["findings"]}
    new_rules = {item["rule_id"] for item in payload["new_findings"]}
    assert "SEC_OS_SYSTEM" in all_rules
    assert "SEC_OS_SYSTEM" not in new_rules
    assert new_rules == {"SEC_NETWORK_TIMEOUT"}


def test_security_scan_ignores_symlink_that_escapes_root(tmp_path: Path, capsys) -> None:
    src = tmp_path / "src"
    src.mkdir()

    outside = tmp_path.parent / "outside_security_scan.py"
    outside.write_text("import os\nos.system('escaped')\n", encoding="utf-8")
    try:
        os.symlink(outside, src / "escaped_link.py")
        assert _run(["scan", "--root", str(tmp_path), "--format", "json", "--fail-on", "none"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["findings"] == []
    finally:
        outside.unlink(missing_ok=True)


def test_security_scan_skips_broken_symlink_without_failing(tmp_path: Path, capsys) -> None:
    src = tmp_path / "src"
    src.mkdir()

    os.symlink(tmp_path / "missing.py", src / "missing_link.py")
    assert _run(["scan", "--root", str(tmp_path), "--format", "json", "--fail-on", "none"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["findings"] == []
