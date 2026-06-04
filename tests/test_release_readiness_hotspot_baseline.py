from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "release_readiness_hotspot_baseline.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "release_readiness_hotspot_baseline_script", _SCRIPT_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
release_readiness_baseline = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(release_readiness_baseline)


def test_build_payload_collects_module_summary(tmp_path: Path) -> None:
    repo_file = tmp_path / "repo.py"
    doctor_file = tmp_path / "doctor.py"
    repo_file.write_text(
        "def alpha():\n    return 1\n\nclass Repo:\n    pass\n",
        encoding="utf-8",
    )
    doctor_file.write_text(
        "def beta():\n    return 2\n\ndef gamma():\n    return 3\n",
        encoding="utf-8",
    )

    payload = release_readiness_baseline.build_payload([repo_file, doctor_file])
    assert payload["schema_version"] == "sdetkit.release-readiness-hotspot-baseline.v1"
    assert payload["summary"]["module_count"] == 2
    assert payload["summary"]["total_function_count"] == 3
    assert payload["summary"]["total_class_count"] == 1


def test_main_writes_artifact(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    module = tmp_path / "module.py"
    module.write_text("def one():\n    return 1\n", encoding="utf-8")
    rc = release_readiness_baseline.main(["--paths", str(module), "--out", str(target)])
    assert rc == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["summary"]["module_count"] == 1
