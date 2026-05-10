from __future__ import annotations

import importlib
from pathlib import Path

from sdetkit.legacy_adapters import continuous_upgrade as continuous_upgrade_aliases


def _load_continuous_upgrade_command_modules() -> dict[str, str]:
    for value in vars(continuous_upgrade_aliases).values():
        if isinstance(value, dict) and "continuous-upgrade-closeout-7" in value:
            return {str(k): str(v) for k, v in value.items()}
    raise RuntimeError("continuous upgrade legacy command map not found")


COMMAND_MODULES = _load_continuous_upgrade_command_modules()


def _build_summary_for_cycle(cycle: int, root: Path) -> dict:
    command = f"continuous-upgrade-closeout-{cycle}"
    module_name = COMMAND_MODULES[command]
    module = importlib.import_module(module_name)

    preferred = f"build_continuous_upgrade_cycle{cycle}_closeout_summary"
    build = getattr(module, preferred, None)

    if build is None:
        candidates = [
            getattr(module, name)
            for name in dir(module)
            if name.startswith("build_continuous_upgrade_") and name.endswith("_summary")
        ]
        if not candidates:
            raise AttributeError(f"{module_name} has no continuous-upgrade summary builder")
        build = candidates[0]

    return build(root)


def expected_evidence_path(cycle: int, root: Path) -> Path:
    return (
        root
        / f"docs/artifacts/continuous-upgrade-cycle{cycle}-closeout-pack/evidence/cycle{cycle}-execution-summary.json"
    )
