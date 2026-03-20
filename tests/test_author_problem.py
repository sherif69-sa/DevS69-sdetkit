from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sdetkit import cli
from sdetkit.author_problem import (
    DockerCommandRunner,
    WorkflowContract,
    bootstrap_workdir,
    build_docker_image,
    load_workflow_contract,
    render_dockerfile_problem,
    run_author_doctor,
    run_authoring_container,
    run_problem_workflow,
    verify_artifacts,
)


class _FakeRunner(DockerCommandRunner):
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def run(self, argv: list[str], *, cwd: Path | None = None):  # type: ignore[override]
        self.calls.append(list(argv))
        return type(
            "Invocation",
            (),
            {"argv": argv, "returncode": 0, "stdout": "ok", "stderr": "", "to_dict": lambda self: {"argv": argv, "returncode": 0, "stdout": "ok", "stderr": ""}},
        )()

    def which(self, program: str) -> str | None:  # type: ignore[override]
        return f"/usr/bin/{program}"


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "author@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Author"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"], cwd=path, check=True, capture_output=True, text=True
    )


def _write_demo_repo(path: Path) -> None:
    (path / "src/demoapp").mkdir(parents=True)
    (path / "tests").mkdir(parents=True)
    (path / "pyproject.toml").write_text(
        """
[project]
name = "demoapp"
version = "0.1.0"
dependencies = []
[project.optional-dependencies]
test = ["pytest>=8"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (path / "src/demoapp/__init__.py").write_text("", encoding="utf-8")
    (path / "src/demoapp/service.py").write_text(
        """
def refresh_state(snapshot):
    return {"value": snapshot["value"], "sequence": snapshot["sequence"]}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (path / "src/demoapp/storage.py").write_text(
        """
def normalize_snapshot(snapshot):
    return dict(snapshot)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (path / "src/demoapp/api.py").write_text(
        """
from demoapp.service import refresh_state
from demoapp.storage import normalize_snapshot


def perform_refresh(snapshot):
    return normalize_snapshot(refresh_state(snapshot))
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (path / "tests/test_existing.py").write_text(
        """
from demoapp.api import perform_refresh


def test_existing_behavior():
    assert perform_refresh({"value": "x", "sequence": 1}) == {"value": "x", "sequence": 1}
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _make_problem_patches(repo_root: Path, workdir: Path) -> None:
    (repo_root / "test.sh").write_text(
        "#!/usr/bin/env bash\n\nset -euo pipefail\n\nmode=${1:-}\ncase \"$mode\" in\n  new) PYTHONPATH=src python3 -m pytest tests/test_refresh_problem.py ;;\n  base) PYTHONPATH=src python3 -m pytest tests --ignore=tests/test_refresh_problem.py ;;\n  *) echo \"Usage: $0 {base|new}\" >&2; exit 2 ;;\nesac\n",
        encoding="utf-8",
    )
    (repo_root / "tests/test_refresh_problem.py").write_text(
        """
from demoapp.api import perform_refresh


def test_refresh_contract_tracks_history_and_checkpoint():
    snapshot = {
        "value": "new",
        "sequence": 5,
        "history": ["old"],
        "rotated": True,
        "source": "sync",
    }
    assert perform_refresh(snapshot) == {
        "value": "new",
        "sequence": 5,
        "history": ("old", "new"),
        "rotated": True,
        "source": "sync",
        "checkpoint": "seq:5",
    }
""".strip()
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "add", "-N", "test.sh", "tests/test_refresh_problem.py"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    test_patch = subprocess.run(
        ["git", "diff", "--binary", "--", "test.sh", "tests/test_refresh_problem.py"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    (workdir / "test.patch").write_text(test_patch, encoding="utf-8")
    subprocess.run(
        ["git", "reset", "--", "test.sh", "tests/test_refresh_problem.py"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    (repo_root / "test.sh").unlink()
    (repo_root / "tests/test_refresh_problem.py").unlink()

    (repo_root / "src/demoapp/service.py").write_text(
        """
def refresh_state(snapshot):
    state = {"value": snapshot["value"], "sequence": snapshot["sequence"]}
    if any(key in snapshot for key in ("history", "rotated", "source")):
        history = list(snapshot.get("history", []))
        history.append(snapshot["value"])
        state.update(
            {
                "history": history,
                "rotated": bool(snapshot.get("rotated", False)),
                "source": snapshot.get("source", "direct"),
                "checkpoint": f"seq:{snapshot['sequence']}",
            }
        )
    return state
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (repo_root / "src/demoapp/storage.py").write_text(
        """
def normalize_snapshot(snapshot):
    normalized = dict(snapshot)
    if "history" in snapshot:
        normalized["history"] = tuple(snapshot.get("history", []))
    return normalized
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (repo_root / "src/demoapp/api.py").write_text(
        """
from demoapp.service import refresh_state
from demoapp.storage import normalize_snapshot


def perform_refresh(snapshot):
    refreshed = refresh_state(snapshot)
    return normalize_snapshot(refreshed)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    solution_patch = subprocess.run(
        [
            "git",
            "diff",
            "--binary",
            "--",
            "src/demoapp/api.py",
            "src/demoapp/service.py",
            "src/demoapp/storage.py",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    (workdir / "solution.patch").write_text(solution_patch, encoding="utf-8")
    subprocess.run(["git", "checkout", "--", "src/demoapp/api.py", "src/demoapp/service.py", "src/demoapp/storage.py"], cwd=repo_root, check=True, capture_output=True, text=True)


def _write_final_metadata(workdir: Path) -> None:
    (workdir / "final_title.txt").write_text(
        "Durable session refresh contract\n", encoding="utf-8"
    )
    (workdir / "final_description.txt").write_text(
        "Implement the repository contract for durable session refresh behavior.\n"
        "- preserve rotation metadata across repeated refresh operations\n"
        "- keep checkpoint sequencing monotonic when stale snapshots arrive late\n"
        "- maintain parity between direct service entrypoints and storage-backed helpers\n"
        "The update must protect rollback-safe state propagation, reject older snapshots once newer sequence markers exist, and ensure normalized refresh payloads keep history, source, and checkpoint details aligned across the public API surface. Repeated calls must remain deterministic even when callers replay previously seen state.\n",
        encoding="utf-8",
    )


def _low_threshold_contract(tmp_path: Path) -> WorkflowContract:
    payload = load_workflow_contract().payload
    copied = json.loads(json.dumps(payload))
    copied["size_gates"]["test_patch_min_bytes"] = 1
    copied["size_gates"]["solution_patch_min_bytes"] = 1
    return WorkflowContract(path=tmp_path / "contract.json", payload=copied)


def test_author_problem_bootstrap_and_contract_load(tmp_path: Path) -> None:
    bootstrap = bootstrap_workdir(tmp_path / "work", topic="Refresh Problem")
    contract = load_workflow_contract()

    assert (tmp_path / "work/current_problem.txt").exists()
    assert (tmp_path / "work/novelty_gate.txt").exists()
    assert (tmp_path / "work/candidate_notes.md").exists()
    assert (tmp_path / "work/test.patch").exists()
    assert contract.size_gates["test_patch_min_bytes"] == 204800
    assert any(item.endswith("submission_001") for item in bootstrap.created)


def test_render_dockerfile_and_docker_helpers(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_demo_repo(repo_root)
    text = render_dockerfile_problem(repo_root)
    runner = _FakeRunner()

    build = build_docker_image(repo_root, runner=runner)
    run = run_authoring_container(repo_root, tmp_path / "work", image="demo-image", runner=runner)

    assert "FROM public.ecr.aws/x8v8d7g8/mars-base:latest" in text
    assert 'CMD ["/bin/bash"]' in text
    assert any("pytest" in line for line in text.splitlines())
    assert build.returncode == 0
    assert run.returncode == 0
    assert runner.calls[0][:3] == ["docker", "build", "-f"]
    assert runner.calls[1][:3] == ["docker", "run", "--rm"]


def test_author_problem_doctor_verify_and_triad(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_demo_repo(repo_root)
    _init_git_repo(repo_root)

    workdir = tmp_path / "work"
    bootstrap_workdir(workdir, topic="refresh")
    _make_problem_patches(repo_root, workdir)
    _write_final_metadata(workdir)
    render_dockerfile_problem(repo_root)
    (workdir / "docker.file").write_text(
        (repo_root / "Dockerfile.problem").read_text(encoding="utf-8"), encoding="utf-8"
    )

    doctor = run_author_doctor(repo_root, workdir, contract=_low_threshold_contract(tmp_path), runner=_FakeRunner())
    summary = verify_artifacts(
        repo_root,
        workdir,
        contract=_low_threshold_contract(tmp_path),
        verify_triad=True,
    )

    assert doctor["inspection"]["repo_name"] == "repo"
    assert summary["ok"] is True
    assert summary["test_patch"]["status"] == "pass"
    assert summary["solution_patch"]["status"] == "pass"
    assert summary["triad"]["ok"] is True
    assert summary["triad"]["phases"][1]["expected"] == "fail"


def test_author_problem_run_emits_failure_summary_when_artifacts_missing(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _write_demo_repo(source)
    _init_git_repo(source)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=source, check=True, capture_output=True, text=True
    ).stdout.strip()

    result = run_problem_workflow(
        str(source),
        sha,
        tmp_path / "work",
        skip_docker=True,
        min_test_patch_bytes=1,
        min_solution_patch_bytes=1,
    )

    assert result.ok is False
    failure = json.loads((tmp_path / "work/final_failure.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "work/run_summary.json").read_text(encoding="utf-8"))
    assert failure["reason"] == "run did not reach a verified artifact bundle"
    assert summary["docker"]["skipped"] is True
    assert summary["repo_url"] == str(source)


def test_main_cli_dispatches_author_problem_init_and_help_lists_author(capsys) -> None:
    rc = cli.main(["author", "problem", "init", "--workdir", "build/work", "--format", "json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["artifact_paths"]["test_patch"].endswith("test.patch")

    help_text = cli._build_root_parser()[0].format_help()
    assert "author" in help_text
