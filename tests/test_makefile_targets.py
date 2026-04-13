from pathlib import Path


def test_makefile_has_bootstrap_and_max_targets() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "Makefile").read_text(encoding="utf-8")
    assert "bootstrap: venv" in text
    assert "max: bootstrap" in text
    assert "bash scripts/bootstrap.sh" in text
    assert "bash quality.sh boost" in text


def test_makefile_has_golden_path_health_target() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "Makefile").read_text(encoding="utf-8")
    assert "golden-path-health: venv" in text
    assert "python scripts/golden_path_health.py" in text


def test_makefile_has_canonical_path_drift_target() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "Makefile").read_text(encoding="utf-8")
    assert "canonical-path-drift: venv" in text
    assert "python scripts/check_canonical_path_drift.py --format json" in text


def test_makefile_has_legacy_command_analyzer_target() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "Makefile").read_text(encoding="utf-8")
    assert "legacy-command-analyzer: venv" in text
    assert "python scripts/legacy_command_analyzer.py --format json" in text


def test_makefile_has_legacy_burndown_target() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "Makefile").read_text(encoding="utf-8")
    assert "legacy-burndown: venv" in text
    assert "python scripts/legacy_burndown.py --format json" in text


def test_makefile_has_adoption_scorecard_target() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "Makefile").read_text(encoding="utf-8")
    assert "adoption-scorecard: venv" in text
    assert "python scripts/adoption_scorecard.py --format json" in text


def test_makefile_has_adoption_scorecard_contract_target() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "Makefile").read_text(encoding="utf-8")
    assert "adoption-scorecard-contract: venv" in text
    assert "python scripts/check_adoption_scorecard_v2_contract.py --format json" in text


def test_makefile_has_observability_contract_target() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "Makefile").read_text(encoding="utf-8")
    assert "observability-contract: venv" in text
    assert "python scripts/check_observability_v2_contract.py --format json" in text


def test_makefile_has_operator_onboarding_wizard_target() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "Makefile").read_text(encoding="utf-8")
    assert "operator-onboarding-wizard: venv" in text
    assert "python scripts/operator_onboarding_wizard.py --format json" in text


def test_makefile_has_primary_docs_map_target() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "Makefile").read_text(encoding="utf-8")
    assert "primary-docs-map: venv" in text
    assert "python scripts/check_primary_docs_map.py --format json" in text
