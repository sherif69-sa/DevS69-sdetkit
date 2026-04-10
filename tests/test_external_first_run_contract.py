from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run(
    cmd: list[str], *, cwd: Path, env: dict[str, str], timeout: int = 240
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def test_canonical_first_path_runs_from_fresh_external_repo(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    external_repo = tmp_path / "external-repo"
    external_repo.mkdir(parents=True)
    (external_repo / "README.md").write_text("# external fixture\n", encoding="utf-8")

    venv_dir = tmp_path / ".venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    python_bin = venv_dir / "bin" / "python"

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    install = _run(
        [str(python_bin), "-m", "pip", "install", str(repo_root)], cwd=external_repo, env=env
    )
    assert install.returncode == 0, (
        "package install failed in blank external repo fixture\n"
        f"stdout:\n{install.stdout}\n"
        f"stderr:\n{install.stderr}"
    )

    commands = (
        (
            [
                str(python_bin),
                "-m",
                "sdetkit",
                "gate",
                "fast",
                "--format",
                "json",
                "--stable-json",
                "--out",
                "build/gate-fast.json",
            ],
            external_repo / "build/gate-fast.json",
            {"ok", "failed_steps", "profile", "steps"},
        ),
        (
            [
                str(python_bin),
                "-m",
                "sdetkit",
                "gate",
                "release",
                "--format",
                "json",
                "--out",
                "build/release-preflight.json",
            ],
            external_repo / "build/release-preflight.json",
            {"ok", "failed_steps", "profile", "steps"},
        ),
        (
            [
                str(python_bin),
                "-m",
                "sdetkit",
                "doctor",
                "--format",
                "json",
                "--out",
                "build/doctor.json",
            ],
            external_repo / "build/doctor.json",
            {"ok", "quality", "recommendations"},
        ),
    )

    outcomes: list[dict[str, object]] = []
    for cmd, artifact_path, required_keys in commands:
        proc = _run(cmd, cwd=external_repo, env=env)
        assert artifact_path.is_file(), (
            f"expected artifact {artifact_path} from `{cmd}`\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        assert required_keys.issubset(payload), f"artifact {artifact_path.name} missing keys"
        outcomes.append(
            {
                "cmd": cmd,
                "returncode": proc.returncode,
                "artifact": str(artifact_path.relative_to(external_repo)),
                "ok": payload.get("ok"),
                "failed_steps": payload.get("failed_steps", []),
            }
        )

    trust_summary = {
        "fixture": "fresh-external-repo",
        "install": "python -m pip install <repo-root>",
        "outcomes": outcomes,
    }
    summary_path = external_repo / "build/external-first-run-proof-summary.json"
    summary_path.write_text(
        json.dumps(trust_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    assert summary_path.is_file()
