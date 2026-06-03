from __future__ import annotations

from pathlib import Path


def _legacy_platform_term() -> str:
    return "".join(("phase", "3"))


def _legacy_completion_term() -> str:
    return "".join(("close", "out"))


def test_dependency_drift_issue_template_uses_platform_readiness_wording() -> None:
    text = Path(".github/ISSUE_TEMPLATE/dependency-drift-weekly.yml").read_text(encoding="utf-8")

    assert "platform-readiness dependency radar JSON" in text
    assert "platform-readiness-dependency-radar-YYYY-MM-DD.json" in text
    assert f"{_legacy_platform_term()} dependency radar" not in text


def test_tekton_reference_descriptions_use_completion_report_wording() -> None:
    paths = [
        Path("examples/ci/tekton/self-hosted-reference-68.yaml"),
        Path("examples/ci/tekton/tekton-self-hosted-reference.yaml"),
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "completion report" in text
        assert _legacy_completion_term() not in text.lower()
