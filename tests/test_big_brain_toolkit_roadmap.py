from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ROADMAP = REPO_ROOT / "docs" / "roadmap" / "big-brain-toolkit-roadmap.md"
MKDOCS = REPO_ROOT / "mkdocs.yml"


def test_big_brain_toolkit_roadmap_captures_strengths_gaps_and_upgrades() -> None:
    text = ROADMAP.read_text(encoding="utf-8")

    assert "## Current strengths after the latest kit run" in text
    assert "## What still needs to become stronger" in text
    assert "## Next upgrade roadmap" in text
    assert "Baseline readiness — Externalize the adaptive intelligence database" in text
    assert "Adoption readiness — Make it enterprise-scale" in text
    assert "Unknown is review-first" in text


def test_big_brain_toolkit_roadmap_is_discoverable_in_mkdocs_nav() -> None:
    text = MKDOCS.read_text(encoding="utf-8")

    assert (
        "Adaptive Intelligence toolkit roadmap: roadmap/adaptive-intelligence-toolkit-roadmap.md"
        in text
    )
