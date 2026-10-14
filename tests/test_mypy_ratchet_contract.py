from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
RATCHET_MODULES = {
    "sdetkit.diagnostic_job",
    "sdetkit.diagnostic_worker_trajectory",
    "sdetkit.failure_vector",
    "sdetkit.safety_gate",
}


def _module_names(override: dict[str, object]) -> set[str]:
    raw = override.get("module", [])
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return {str(item) for item in raw}
    return set()


def test_selected_modules_are_removed_from_blanket_mypy_suppression() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    overrides = config["tool"]["mypy"]["overrides"]

    blanket = [override for override in overrides if _module_names(override) == {"sdetkit.*"}]
    assert len(blanket) == 1
    assert blanket[0].get("ignore_errors") is True

    ratchets = [override for override in overrides if _module_names(override) == RATCHET_MODULES]
    assert len(ratchets) == 1
    assert ratchets[0].get("ignore_errors") is False
