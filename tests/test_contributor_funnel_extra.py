from __future__ import annotations

from sdetkit import contributor_funnel as cf


def test_validate_backlog_errors_and_issue_pack(tmp_path) -> None:
    short = [{"id": "X", "acceptance": ["a"]}]
    errs = cf.validate_backlog(short)
    assert "expected 10 issues" in errs[0]
    assert "fewer than 3 acceptance" in errs[1]

    backlog = cf.build_backlog("docs")[:1]
    cf._write_issue_pack(backlog, str(tmp_path / "pack"))
    out = tmp_path / "pack" / f"{backlog[0]['id'].lower()}.md"
    assert out.exists()


def test_main_strict_fails_when_full_backlog_invalid(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cf,
        "build_backlog",
        lambda area="all": [
            {"id": "X", "area": "docs", "estimate": "S", "title": "t", "acceptance": ["a"]}
        ],
    )
    rc = cf.main(["--strict", "--format", "json"])
    assert rc == 1
    assert "day8-validation" in capsys.readouterr().out
