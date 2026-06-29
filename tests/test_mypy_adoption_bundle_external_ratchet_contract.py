from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
ADOPTION_BUNDLE_EXTERNAL_RATCHET_MODULES = {
    "sdetkit.adoption_evidence_bundle",
    "sdetkit.adoption_external_integration",
}


def _module_names(override: dict[str, object]) -> set[str]:
    raw = override.get("module", [])
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return {str(item) for item in raw}
    return set()


def test_adoption_bundle_and_external_integration_are_type_checked() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    overrides = config["tool"]["mypy"]["overrides"]

    ratchets = [
        override
        for override in overrides
        if _module_names(override) == ADOPTION_BUNDLE_EXTERNAL_RATCHET_MODULES
    ]
    assert len(ratchets) == 1
    assert ratchets[0].get("ignore_errors") is False
