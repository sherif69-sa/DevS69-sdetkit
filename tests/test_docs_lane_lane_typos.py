from __future__ import annotations

from pathlib import Path


def test_integration_closeout_docs_do_not_contain_lane_lane_typo() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []
    for path in sorted((repo_root / "docs").glob("integrations-*.md")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if "Lane lane" in line:
                offenders.append(f"{path.relative_to(repo_root)}:{line_no}")
    assert not offenders, "Found 'Lane lane' typo in:\n" + "\n".join(offenders)
