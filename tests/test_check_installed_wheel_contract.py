from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


def _load_module():
    script = (
        Path(__file__).resolve().parent.parent / "tests" / "contract" / "check_installed_wheel.py"
    )
    spec = importlib.util.spec_from_file_location("check_installed_wheel_contract", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_preserves_virtualenv_python_path(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    requested_python = Path(".venv-smoke/bin/python")
    calls: list[tuple[Path, tuple[str, ...]]] = []

    def fake_run(cli_python: Path, repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        calls.append((cli_python, args))
        if args[:2] == ("integration", "check"):
            payload = {
                "summary": {"failed": 1, "passed": False},
                "checks": [{"kind": "env", "name": "CI"}],
            }
            return subprocess.CompletedProcess(
                [str(cli_python), "-m", "sdetkit", *args],
                1,
                stdout=json.dumps(payload),
                stderr="",
            )
        if args[:2] == ("forensics", "bundle"):
            bundle_path = repo_root / "build" / "installed-wheel-bundle.zip"
            bundle_path.parent.mkdir(parents=True, exist_ok=True)
            import zipfile

            with zipfile.ZipFile(bundle_path, "w") as zf:
                zf.writestr("manifest.json", "{}")
                zf.writestr("run.json", "{}")
            return subprocess.CompletedProcess(
                [str(cli_python), "-m", "sdetkit", *args], 0, stdout="", stderr=""
            )
        payload = {}
        if args[:2] == ("kits", "list"):
            payload = {
                "kits": [
                    {"slug": slug}
                    for slug in ["forensics", "integration", "release", "intelligence"]
                ]
            }
        elif args[:3] == ("intelligence", "flake", "classify"):
            payload = {
                "summary": {"flaky": 1, "stable_failing": 0, "stable_passing": 1},
                "tests": [{"fingerprint": "fp-1"}],
            }
        elif args[:2] == ("forensics", "compare"):
            payload = {"regression_summary": {"changed_failures": 1, "new_failures": 1}}
        return subprocess.CompletedProcess(
            [str(cli_python), "-m", "sdetkit", *args], 0, stdout=json.dumps(payload), stderr=""
        )

    monkeypatch.setattr(module, "_run", fake_run)

    rc = module.main(["--python", str(requested_python), "--repo-root", str(tmp_path)])

    assert rc == 0
    assert calls
    assert all(cli_python == requested_python for cli_python, _ in calls)
