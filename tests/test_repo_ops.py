from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from sdetkit import cli


def _invoke(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = cli.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def test_repo_ops_json_payload(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "releasing.md").write_text("# release\n", encoding="utf-8")
    (tmp_path / "SECURITY.md").write_text("# security\n", encoding="utf-8")

    code, out, _ = _invoke(
        ["repo", "ops", str(tmp_path), "--allow-absolute-path", "--format", "json"]
    )
    payload = json.loads(out)

    assert code == 1
    assert payload["schema_version"] == "sdetkit.ops.v1"
    assert payload["summary"]["checks"] == 9
    assert "prioritized_recommendations" in payload


def test_repo_ops_min_score_pass(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "incident-response.md").write_text("# ir\n", encoding="utf-8")
    (tmp_path / "docs" / "oncall.md").write_text("# oncall\n", encoding="utf-8")
    (tmp_path / "docs" / "releasing.md").write_text("# release\n", encoding="utf-8")
    (tmp_path / "docs" / "security.md").write_text("# security\n", encoding="utf-8")
    (tmp_path / "runbooks").mkdir()
    (tmp_path / "monitoring").mkdir()
    (tmp_path / "slo.yaml").write_text("service: api\n", encoding="utf-8")
    (tmp_path / "DISASTER_RECOVERY.md").write_text("# dr\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "CODEOWNERS").write_text("* @acme/team\n", encoding="utf-8")

    code, out, _ = _invoke(
        ["repo", "ops", str(tmp_path), "--allow-absolute-path", "--min-score", "90"]
    )

    assert code == 0
    assert "Status:" in out
    assert "Score:" in out


def test_repo_ops_output_file(tmp_path: Path) -> None:
    output = tmp_path / "ops.json"
    code, _, _ = _invoke(
        [
            "repo",
            "ops",
            str(tmp_path),
            "--allow-absolute-path",
            "--format",
            "json",
            "--output",
            str(output),
            "--force",
            "--min-score",
            "0",
        ]
    )

    assert code == 0
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "sdetkit.ops.v1"
