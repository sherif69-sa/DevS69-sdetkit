from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from sdetkit import cli
from sdetkit.author_problem import (
    DockerCommandRunner,
    WorkflowContract,
    _git_restore_paths,
    _reset_checkout_dir,
    _rich_strategy_matches,
    bootstrap_workdir,
    build_docker_image,
    load_workflow_contract,
    render_dockerfile_problem,
    run_author_doctor,
    run_authoring_container,
    run_problem_workflow,
    verify_artifacts,
)


def _export_dir(root: Path) -> Path:
    return root / "artifacts" / "platform_problem" / "latest"


class _FakeRunner(DockerCommandRunner):
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def run(self, argv: list[str], *, cwd: Path | None = None):  # type: ignore[override]
        self.calls.append(list(argv))
        return type(
            "Invocation",
            (),
            {
                "argv": argv,
                "returncode": 0,
                "stdout": "ok",
                "stderr": "",
                "to_dict": lambda self: {
                    "argv": argv,
                    "returncode": 0,
                    "stdout": "ok",
                    "stderr": "",
                },
            },
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


def _write_rich_repo(path: Path) -> None:
    (path / "rich").mkdir(parents=True)
    (path / "tests").mkdir(parents=True)
    (path / "pyproject.toml").write_text(
        """
[project]
name = "rich"
version = "0.1.0"
dependencies = []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (path / "rich/__init__.py").write_text("", encoding="utf-8")
    (path / "rich/text.py").write_text("class Text: ...\n", encoding="utf-8")
    (path / "tests/test_text.py").write_text(
        "def test_placeholder():\n    assert True\n", encoding="utf-8"
    )


def _write_rich_poetry_repo(path: Path) -> None:
    (path / "rich").mkdir(parents=True)
    (path / "tests").mkdir(parents=True)
    (path / "pyproject.toml").write_text(
        """
[tool.poetry]
name = "rich"
version = "0.1.0"
description = "rich"
authors = ["Author <author@example.com>"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (path / "rich/__init__.py").write_text("", encoding="utf-8")
    (path / "rich/text.py").write_text("class Text: ...\n", encoding="utf-8")
    (path / "tests/test_text.py").write_text(
        "def test_placeholder():\n    assert True\n", encoding="utf-8"
    )


def _make_problem_patches(repo_root: Path, workdir: Path) -> None:
    (repo_root / "test.sh").write_text(
        '#!/usr/bin/env bash\n\nset -euo pipefail\n\nmode=${1:-}\ncase "$mode" in\n  new) PYTHONPATH=src python3 -m pytest tests/test_refresh_problem.py ;;\n  base) PYTHONPATH=src python3 -m pytest tests --ignore=tests/test_refresh_problem.py ;;\n  *) echo "Usage: $0 {base|new}" >&2; exit 2 ;;\nesac\n',
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
    subprocess.run(
        [
            "git",
            "checkout",
            "--",
            "src/demoapp/api.py",
            "src/demoapp/service.py",
            "src/demoapp/storage.py",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _write_final_metadata(workdir: Path) -> None:
    (workdir / "final_title.txt").write_text("Durable session refresh contract\n", encoding="utf-8")
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
    assert "--user" in runner.calls[1]
    user_index = runner.calls[1].index("--user")
    assert runner.calls[1][user_index + 1] == f"{os.getuid()}:{os.getgid()}"


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

    doctor = run_author_doctor(
        repo_root, workdir, contract=_low_threshold_contract(tmp_path), runner=_FakeRunner()
    )
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
    (source / "pkg").mkdir()
    (source / "tests").mkdir()
    (source / "pyproject.toml").write_text(
        """
[project]
name = "minimal"
version = "0.1.0"
dependencies = []
[project.optional-dependencies]
test = ["pytest>=8"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (source / "pkg/__init__.py").write_text("", encoding="utf-8")
    (source / "pkg/core.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    (source / "tests/test_existing.py").write_text(
        "from pkg.core import value\n\ndef test_value():\n    assert value() == 1\n",
        encoding="utf-8",
    )
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
        artifact_export_root=tmp_path,
    )

    assert result.ok is False
    failure = json.loads((tmp_path / "work/final_failure.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "work/run_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (_export_dir(tmp_path) / "export_manifest.json").read_text(encoding="utf-8")
    )
    assert (
        failure["reason"]
        == "no automated authoring strategy matched target repository after baseline and fit gating"
    )
    assert summary["verification"]["ok"] is False
    assert (_export_dir(tmp_path) / "final_failure.json").exists()
    assert manifest["success"] is False
    assert manifest["exports"]["final_failure.json"]["source"].endswith("/work/final_failure.json")


def test_author_problem_run_can_succeed_end_to_end_with_demo_fixture(tmp_path: Path) -> None:
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
        artifact_export_root=tmp_path,
    )

    assert result.ok is True
    summary = json.loads((tmp_path / "work/run_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (_export_dir(tmp_path) / "export_manifest.json").read_text(encoding="utf-8")
    )
    assert (tmp_path / "work/test.patch").exists()
    assert (tmp_path / "work/solution.patch").exists()
    assert (tmp_path / "work/docker.file").exists()
    assert summary["docker"]["skipped"] is True
    assert summary["repo_url"] == str(source)
    assert summary["verification"]["ok"] is True
    for name in [
        "test.patch",
        "solution.patch",
        "docker.file",
        "final_title.txt",
        "final_description.txt",
        "run_summary.json",
    ]:
        assert (_export_dir(tmp_path) / name).exists()
    assert not (_export_dir(tmp_path) / "final_failure.json").exists()
    assert manifest["success"] is True
    assert manifest["exports"]["run_summary.json"]["destination"].endswith(
        "artifacts/platform_problem/latest/run_summary.json"
    )


def test_author_problem_run_reuses_existing_workdir_app_checkout(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _write_demo_repo(source)
    _init_git_repo(source)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=source, check=True, capture_output=True, text=True
    ).stdout.strip()
    workdir = tmp_path / "work"

    first = run_problem_workflow(
        str(source),
        sha,
        workdir,
        skip_docker=True,
        min_test_patch_bytes=1,
        min_solution_patch_bytes=1,
        artifact_export_root=tmp_path,
    )
    assert first.ok is True
    assert (workdir / "app").exists()

    second = run_problem_workflow(
        str(source),
        sha,
        workdir,
        skip_docker=True,
        min_test_patch_bytes=1,
        min_solution_patch_bytes=1,
        artifact_export_root=tmp_path,
    )

    assert second.ok is True
    summary = json.loads((workdir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["verification"]["ok"] is True


def test_rich_strategy_matches_repo_metadata_without_checkout_name_hint(tmp_path: Path) -> None:
    checkout = tmp_path / "work" / "app"
    checkout.mkdir(parents=True)
    _write_rich_repo(checkout)

    assert checkout.name != "rich"
    assert _rich_strategy_matches(checkout) is True


def test_rich_strategy_matches_poetry_metadata_layout(tmp_path: Path) -> None:
    checkout = tmp_path / "clone" / "app"
    checkout.mkdir(parents=True)
    _write_rich_poetry_repo(checkout)

    assert _rich_strategy_matches(checkout) is True


def test_rich_problem_generator_executes(tmp_path: Path) -> None:
    output = tmp_path / "test_markup_roundtrip_problem.py"
    script = Path("templates/platform_problem/rich/generate_test_problem.py")
    rich_pkg = tmp_path / "rich"
    rich_pkg.mkdir()
    (rich_pkg / "__init__.py").write_text("", encoding="utf-8")
    (rich_pkg / "console.py").write_text("class Console:\n    pass\n", encoding="utf-8")
    (rich_pkg / "style.py").write_text(
        "class Style:\n"
        "    def __init__(self, link='', meta=None):\n"
        "        self.link = link\n"
        "        self.meta = meta or {}\n",
        encoding="utf-8",
    )
    (rich_pkg / "text.py").write_text(
        """
from dataclasses import dataclass


@dataclass
class _Fragment:
    plain: str
    justify: str
    overflow: str
    no_wrap: bool
    end: str
    tab_size: int


class Text:
    def __init__(self, plain, style=""):
        self.plain = plain
        self.style = style
        self.justify = ""
        self.overflow = ""
        self.no_wrap = False
        self.end = ""
        self.tab_size = 8
        self._spans = []

    def __len__(self):
        return len(self.plain)

    def stylize(self, style, start=0, end=None):
        self._spans.append((style, start, len(self.plain) if end is None else end))

    @property
    def markup(self):
        return repr((self.plain, self.style, self.justify, self.overflow, self.no_wrap, self.end, self.tab_size, len(self._spans)))

    @classmethod
    def from_markup(cls, markup, justify="", overflow="", no_wrap=False, end="", tab_size=8):
        text = cls(markup)
        text.justify = justify
        text.overflow = overflow
        text.no_wrap = no_wrap
        text.end = end
        text.tab_size = tab_size
        return text

    def divide(self, offsets):
        points = [0, *offsets, len(self.plain)]
        fragments = []
        for start, stop in zip(points, points[1:]):
            fragments.append(
                _Fragment(
                    plain=self.plain[start:stop],
                    justify=self.justify,
                    overflow=self.overflow,
                    no_wrap=self.no_wrap,
                    end=self.end,
                    tab_size=self.tab_size,
                )
            )
        return fragments
""".strip()
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["python", str(script), str(output)],
        check=True,
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
    )

    rendered = output.read_text(encoding="utf-8")
    assert "def test_markup_roundtrip_problem_cases()" in rendered
    assert "def test_fragment_metadata_problem_cases()" in rendered


def test_git_restore_paths_restores_tracked_and_deletes_untracked(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "tracked.py").write_text("value = 1\n", encoding="utf-8")
    _init_git_repo(repo)

    (repo / "tracked.py").write_text("value = 2\n", encoding="utf-8")
    (repo / "new_helper.py").write_text("helper = True\n", encoding="utf-8")

    _git_restore_paths(repo, ["tracked.py", "new_helper.py"])

    assert (repo / "tracked.py").read_text(encoding="utf-8") == "value = 1\n"
    assert not (repo / "new_helper.py").exists()


def test_reset_checkout_dir_quarantines_stale_tree_when_rmtree_hits_permission_error(
    tmp_path: Path, monkeypatch
) -> None:
    app_dir = tmp_path / "app"
    (app_dir / "__pycache__").mkdir(parents=True)
    (app_dir / "__pycache__" / "test_progress.cpython-312-pytest-9.0.2.pyc").write_bytes(b"pyc")
    original_rmtree = shutil.rmtree
    seen_paths: list[str] = []

    def fake_rmtree(path, *args, **kwargs):
        target = Path(path)
        seen_paths.append(target.name)
        if target == app_dir:
            raise PermissionError("stale root-owned pycache")
        return original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", fake_rmtree)

    _reset_checkout_dir(app_dir)

    assert not app_dir.exists()
    assert any(name.startswith("app.stale.") for name in seen_paths)
    assert not any(tmp_path.glob("app.stale.*"))


def test_main_cli_dispatches_author_problem_init_and_help_lists_author(capsys) -> None:
    rc = cli.main(["author", "problem", "init", "--workdir", "build/work", "--format", "json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["artifact_paths"]["test_patch"].endswith("test.patch")

    help_text = cli._build_root_parser()[0].format_help()
    assert "author" in help_text
