from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


def _script_path() -> Path:
    return (
        Path(__file__).resolve().parent.parent / "tests" / "contract" / "check_installed_wheel.py"
    )


def _load_module():
    script = _script_path()
    spec = importlib.util.spec_from_file_location("check_installed_wheel_contract", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_exposes_executable_command_line_entrypoint() -> None:
    proc = subprocess.run(
        [sys.executable, str(_script_path()), "--help"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    assert "Run installed-wheel CLI contract checks." in proc.stdout


def test_main_preserves_virtualenv_python_path(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    requested_python = Path(".venv-smoke/bin/python")
    expected_python = Path(os.path.abspath(requested_python))
    calls: list[tuple[Path, tuple[str, ...]]] = []
    module_calls: list[tuple[Path, str, tuple[str, ...]]] = []

    def fake_run(cli_python: Path, repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        calls.append((cli_python, args))
        command = [str(cli_python), "-m", "sdetkit", *args]

        if args[:2] == ("integration", "check"):
            payload = {
                "summary": {"failed": 0, "passed": True, "total": 0},
                "checks": [],
            }
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

        if args[:2] == ("forensics", "bundle"):
            bundle_path = repo_root / "build" / "installed-wheel-bundle.zip"
            bundle_path.parent.mkdir(parents=True, exist_ok=True)
            import zipfile

            with zipfile.ZipFile(bundle_path, "w") as zf:
                zf.writestr("manifest.json", "{}")
                zf.writestr("run.json", "{}")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        if args[:1] == ("adoption-surface",):
            out_path = Path(args[args.index("--out") + 1])
            out_path.write_text(
                json.dumps(
                    {
                        "detected_languages": [{"name": "cpp"}, {"name": "python"}],
                        "authority_boundary": {
                            "automation_allowed": False,
                            "patch_application_allowed": False,
                            "merge_authorized": False,
                            "semantic_equivalence_proven": False,
                        },
                    }
                ),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        if args[:2] == ("security", "scan"):
            sarif_path = Path(args[args.index("--output") + 1])
            sbom_path = Path(args[args.index("--sbom-output") + 1])
            sarif_path.write_text("{}\n", encoding="utf-8")
            sbom_path.write_text("{}\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        if args[:2] == ("investigate", "failure"):
            payload = {
                "classification": "PYTEST_ASSERTION_FAILURE",
                "automation_allowed": False,
            }
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

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
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    def fake_run_module(
        cli_python: Path,
        repo_root: Path,
        module_name: str,
        *args: str,
    ) -> subprocess.CompletedProcess[str]:
        module_calls.append((cli_python, module_name, args))
        command = [str(cli_python), "-m", module_name, *args]
        denied = {
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        }

        if module_name == "sdetkit.cpp_operator_proof":
            out_dir = Path(args[args.index("--out-dir") + 1])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "cpp-operator-proof.json").write_text("{}\n", encoding="utf-8")
            payload = {
                "verification_ok": False,
                "authority_boundary": denied,
            }
            return subprocess.CompletedProcess(command, 1, stdout=json.dumps(payload), stderr="")

        if module_name == "sdetkit.remediation_research_contract":
            payload = {
                "report_status": "review_required",
                "readiness_reasons": [
                    "scenario_outcome_mismatch:unsafe_patch:expected=blocked:actual=pass"
                ],
                "authority_boundary": denied,
            }
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

        raise AssertionError(f"unexpected module invocation: {module_name} {args!r}")

    monkeypatch.setattr(module, "_run", fake_run)
    monkeypatch.setattr(module, "_run_module", fake_run_module)

    rc = module.main(["--python", str(requested_python), "--repo-root", str(tmp_path)])

    assert rc == 0
    assert calls
    assert module_calls
    assert all(cli_python == expected_python for cli_python, _ in calls)
    assert all(cli_python == expected_python for cli_python, _, _ in module_calls)
    assert expected_python != Path(sys.executable).resolve()


def test_run_clears_ci_environment_for_local_smoke(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setenv("CI", "true")

    captured: dict[str, str | None] = {}

    def fake_subprocess_run(*args, **kwargs):
        env = kwargs.get("env", {})
        captured["CI"] = env.get("CI")
        return subprocess.CompletedProcess(args[0], 0, stdout="{}", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_subprocess_run)

    module._run(Path(".venv-smoke/bin/python"), tmp_path, "kits", "list", "--format", "json")

    assert captured["CI"] is None
