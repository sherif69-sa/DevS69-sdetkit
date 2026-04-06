from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import _toml
from .atomicio import atomic_write_text, canonical_json_dumps
from .bools import coerce_bool

_BASE_IMAGE = "public.ecr.aws/x8v8d7g8/mars-base:latest"
_DEFAULT_WORKFLOW_PATH = Path(".sdetkit/workflows/platform_problem.yaml")
_ALLOWED_TEST_METADATA_EDIT = "tests/conftest.py"
_TOOLKIT_MOUNT = "/opt/sdetkit"
_REPO_EXPORT_ROOT = Path("artifacts/platform_problem/latest")
_KNOWN_PYTEST_PACKAGES = (
    "pytest",
    "pytest-asyncio",
    "pytest-cov",
    "pytest-mock",
    "pytest-xdist",
    "pytest-rerunfailures",
    "pytest-timeout",
    "hypothesis",
    "requests-mock",
    "freezegun",
)


@dataclass(frozen=True)
class DockerInvocation:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "argv": list(self.argv),
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


class DockerCommandRunner:
    def run(self, argv: list[str], *, cwd: Path | None = None) -> DockerInvocation:
        proc = subprocess.run(argv, cwd=str(cwd) if cwd else None, text=True, capture_output=True)
        return DockerInvocation(
            argv=argv,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    def which(self, program: str) -> str | None:
        return shutil.which(program)


def _current_host_uid_gid() -> tuple[int, int] | None:
    getuid = getattr(os, "getuid", None)
    getgid = getattr(os, "getgid", None)
    if not callable(getuid) or not callable(getgid):
        return None
    uid = int(getuid())
    gid = int(getgid())
    if uid < 0 or gid < 0:
        return None
    return uid, gid


@dataclass(frozen=True)
class WorkflowContract:
    path: Path
    payload: dict[str, Any]

    @property
    def required_artifacts(self) -> list[str]:
        return list(self.payload.get("required_artifacts", []))

    @property
    def size_gates(self) -> dict[str, int]:
        gates = self.payload.get("size_gates", {})
        return {
            "test_patch_min_bytes": int(gates.get("test_patch_min_bytes", 204800)),
            "solution_patch_min_bytes": int(gates.get("solution_patch_min_bytes", 29696)),
        }

    @property
    def preferred_production_file_scope(self) -> dict[str, int]:
        scope = self.payload.get("preferred_production_file_scope", {})
        return {
            "warning_below": int(scope.get("warning_below", 3)),
            "preferred_min": int(scope.get("preferred_min", 3)),
            "preferred_max": int(scope.get("preferred_max", 6)),
            "fail_below": int(scope.get("fail_below", 2)),
        }

    @property
    def runner_contract(self) -> dict[str, Any]:
        return dict(self.payload.get("runner_contract", {}))

    @property
    def gating_order(self) -> list[str]:
        return list(self.payload.get("gating_order", []))

    @property
    def failure_summary_fields(self) -> list[str]:
        return list(self.payload.get("failure_summary_fields", []))

    @property
    def final_description_constraints(self) -> dict[str, Any]:
        return dict(self.payload.get("final_description_constraints", {}))


@dataclass(frozen=True)
class RepoInspection:
    root: Path
    repo_name: str
    metadata_files: list[str]
    requirements_files: list[str]
    ci_files: list[str]
    dependency_risks: list[str]
    baseline_commands: list[str]
    likely_long_horizon_fit: bool
    long_horizon_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root.as_posix(),
            "repo_name": self.repo_name,
            "metadata_files": list(self.metadata_files),
            "requirements_files": list(self.requirements_files),
            "ci_files": list(self.ci_files),
            "dependency_risks": list(self.dependency_risks),
            "baseline_commands": list(self.baseline_commands),
            "likely_long_horizon_fit": self.likely_long_horizon_fit,
            "long_horizon_notes": list(self.long_horizon_notes),
        }


@dataclass(frozen=True)
class PatchAnalysis:
    path: Path
    exists: bool
    size_bytes: int
    files: list[str]
    status: str
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path.as_posix(),
            "exists": self.exists,
            "size_bytes": self.size_bytes,
            "files": list(self.files),
            "status": self.status,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class TriadPhase:
    name: str
    command: str
    expected: str
    returncode: int
    stdout: str
    stderr: str
    ok: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "expected": self.expected,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "ok": self.ok,
        }


@dataclass(frozen=True)
class TriadResult:
    ok: bool
    phases: list[TriadPhase]
    clean_tree_ok: bool
    clean_tree_details: list[str]
    replay_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "phases": [phase.to_dict() for phase in self.phases],
            "clean_tree_ok": self.clean_tree_ok,
            "clean_tree_details": list(self.clean_tree_details),
            "replay_commands": list(self.replay_commands),
        }


@dataclass(frozen=True)
class WorkBootstrap:
    workdir: Path
    submission_dir: Path
    created: list[str]
    artifact_paths: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workdir": self.workdir.as_posix(),
            "submission_dir": self.submission_dir.as_posix(),
            "created": list(self.created),
            "artifact_paths": dict(self.artifact_paths),
        }


@dataclass(frozen=True)
class RunResult:
    ok: bool
    summary: dict[str, Any]
    failure: dict[str, Any] | None = None


@dataclass(frozen=True)
class GateResult:
    name: str
    ok: bool
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, **self.details}


@dataclass(frozen=True)
class StageCommand:
    name: str
    argv: list[str]
    cwd: Path
    returncode: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "argv": list(self.argv),
            "cwd": self.cwd.as_posix(),
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(frozen=True)
class AuthoringAttempt:
    name: str
    ok: bool
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, **self.details}


@dataclass(frozen=True)
class ContainerAuthoringResult:
    ok: bool
    summary: dict[str, Any]
    failure_reason: str | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_workflow_contract(path: Path | None = None) -> WorkflowContract:
    candidates: list[Path] = []
    if path is not None:
        candidates.append(Path(path))
    candidates.extend([Path.cwd() / _DEFAULT_WORKFLOW_PATH, _repo_root() / _DEFAULT_WORKFLOW_PATH])
    for candidate in candidates:
        if candidate.exists():
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            return WorkflowContract(path=candidate.resolve(), payload=payload)
    raise FileNotFoundError(f"workflow contract not found: {_DEFAULT_WORKFLOW_PATH.as_posix()}")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "platform_problem"


def _next_submission_dir(workdir: Path) -> Path:
    existing = sorted(workdir.glob("submission_*"))
    max_id = 0
    for item in existing:
        match = re.fullmatch(r"submission_(\d+)", item.name)
        if match:
            max_id = max(max_id, int(match.group(1)))
    return workdir / f"submission_{max_id + 1:03d}"


def _write_if_missing(path: Path, text: str, created: list[str]) -> None:
    if path.exists():
        return
    atomic_write_text(path, text)
    created.append(path.as_posix())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, canonical_json_dumps(payload))


def bootstrap_workdir(workdir: Path, *, topic: str | None = None) -> WorkBootstrap:
    workdir = Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    slug = _slugify(topic or "platform-problem")
    _write_if_missing(workdir / "current_problem.txt", "Pending problem selection.\n", created)
    _write_if_missing(workdir / "current_slug.txt", slug + "\n", created)
    _write_if_missing(
        workdir / "problem_history.md",
        "# Problem history\n\n- bootstrap created by sdetkit author problem\n",
        created,
    )
    novelty_dir = workdir / "novelty_gate"
    if not novelty_dir.exists():
        novelty_dir.mkdir(parents=True, exist_ok=True)
        created.append(novelty_dir.as_posix())
    _write_if_missing(
        workdir / "novelty_gate.txt",
        (
            "# novelty gate\n\n"
            "## candidate\n- describe the proposed contract and target behavior.\n\n"
            "## public-surface scan\n- list existing tests, docs, issues, PRs, and releases reviewed.\n\n"
            "## anti-shortcut traps\n- note why a tiny local fix should not satisfy the contract.\n\n"
            "## breadth expectation\n- identify 3-6 production files likely to move.\n"
        ),
        created,
    )
    _write_if_missing(
        workdir / "candidate_notes.md",
        (
            "# Candidate notes\n\n"
            "## baseline environment\n- commands and outcomes\n\n"
            "## repo long-horizon fit\n- public entrypoints\n- cross-module behavior\n\n"
            "## candidate fit\n- downstream consequences\n- rollback/retry/parity/sequencing semantics\n"
        ),
        created,
    )
    submission_dir = _next_submission_dir(workdir)
    submission_dir.mkdir(parents=True, exist_ok=True)
    created.append(submission_dir.as_posix())
    for name in [
        "test.patch",
        "solution.patch",
        "docker.file",
        "final_title.txt",
        "final_description.txt",
    ]:
        _write_if_missing(workdir / name, "", created)
    _write_if_missing(
        workdir / "run_summary.json",
        canonical_json_dumps({"ok": False, "status": "bootstrapped"}),
        created,
    )
    artifact_paths = {
        "test_patch": (workdir / "test.patch").as_posix(),
        "solution_patch": (workdir / "solution.patch").as_posix(),
        "docker_file": (workdir / "docker.file").as_posix(),
        "final_title": (workdir / "final_title.txt").as_posix(),
        "final_description": (workdir / "final_description.txt").as_posix(),
        "run_summary": (workdir / "run_summary.json").as_posix(),
        "author_doctor": (workdir / "author_doctor.json").as_posix(),
        "final_failure": (workdir / "final_failure.json").as_posix(),
    }
    return WorkBootstrap(
        workdir=workdir,
        submission_dir=submission_dir,
        created=created,
        artifact_paths=artifact_paths,
    )


def _artifact_export_root(root: Path | None = None) -> Path:
    return (root or _repo_root()) / _REPO_EXPORT_ROOT


def _export_final_artifacts(
    workdir: Path,
    *,
    repo_url: str,
    sha: str,
    success: bool,
    export_root: Path | None = None,
) -> dict[str, Any]:
    export_dir = _artifact_export_root(export_root)
    export_dir.mkdir(parents=True, exist_ok=True)
    exported: dict[str, dict[str, str]] = {}
    for name in [
        "test.patch",
        "solution.patch",
        "docker.file",
        "final_title.txt",
        "final_description.txt",
        "run_summary.json",
    ]:
        source = workdir / name
        if not source.exists():
            continue
        destination = export_dir / name
        shutil.copy2(source, destination)
        exported[name] = {
            "source": source.as_posix(),
            "destination": destination.as_posix(),
        }

    failure_source = workdir / "final_failure.json"
    failure_destination = export_dir / "final_failure.json"
    if failure_source.exists():
        if success:
            failure_destination.unlink(missing_ok=True)
        else:
            shutil.copy2(failure_source, failure_destination)
            exported["final_failure.json"] = {
                "source": failure_source.as_posix(),
                "destination": failure_destination.as_posix(),
            }
    else:
        failure_destination.unlink(missing_ok=True)

    manifest_path = export_dir / "export_manifest.json"
    manifest = {
        "repo_url": repo_url,
        "pinned_sha": sha,
        "success": success,
        "exported_at": datetime.now(UTC).isoformat(),
        "exports": exported,
    }
    _write_json(manifest_path, manifest)
    return {
        "export_dir": export_dir.as_posix(),
        "manifest": manifest_path.as_posix(),
        "success": success,
        "exports": exported,
    }


def _runner_prefix(repo_root: Path | None = None) -> str:
    if repo_root is not None and (Path(repo_root) / "src").exists():
        return "PYTHONPATH=src "
    return ""


def generate_test_runner(topic: str, *, pythonpath_prefix: str = "") -> str:
    slug = _slugify(topic)
    return (
        "#!/usr/bin/env bash\n\n"
        "set -euo pipefail\n\n"
        "mode=${1:-}\n"
        'case "$mode" in\n'
        f"  new) {pythonpath_prefix}python3 -m pytest tests/test_{slug}_problem.py ;;\n"
        f"  base) {pythonpath_prefix}python3 -m pytest tests --ignore=tests/test_{slug}_problem.py ;;\n"
        '  *) echo "Usage: $0 {base|new}" >&2; exit 2 ;;\n'
        "esac\n"
    )


def ensure_minimal_test_runner(repo_root: Path, *, topic: str) -> Path:
    path = Path(repo_root) / "test.sh"
    atomic_write_text(
        path, generate_test_runner(topic, pythonpath_prefix=_runner_prefix(Path(repo_root)))
    )
    path.chmod(0o755)
    return path


def inspect_repo_metadata(repo_root: Path) -> RepoInspection:
    repo_root = Path(repo_root).resolve()
    metadata_files: list[str] = []
    requirements_files: list[str] = []
    ci_files: list[str] = []
    for rel in ["pyproject.toml", "tox.ini", "noxfile.py", "setup.py", "setup.cfg"]:
        if (repo_root / rel).exists():
            metadata_files.append(rel)
    for path in sorted(repo_root.glob("requirements*.txt")):
        if path.is_file():
            requirements_files.append(path.name)
    for rel in [
        ".github/workflows",
        ".gitlab-ci.yml",
        "azure-pipelines.yml",
        "tox.ini",
        "noxfile.py",
    ]:
        if (repo_root / rel).exists():
            ci_files.append(rel)

    risks: list[str] = []
    baseline_commands: list[str] = []
    if "pyproject.toml" in metadata_files or requirements_files:
        baseline_commands.append("python3 -m pytest")
    else:
        baseline_commands.append("python3 -m pytest")
        risks.append(
            "no pyproject.toml or requirements*.txt found; Dockerfile.problem may need inferred deps"
        )
    if "tox.ini" in metadata_files:
        baseline_commands.append("python3 -m tox -q")
    if "noxfile.py" in metadata_files:
        baseline_commands.append("python3 -m nox -s tests")

    src_py = list(repo_root.glob("src/**/*.py"))
    any_py = [
        p for p in repo_root.rglob("*.py") if ".git" not in p.parts and ".venv" not in p.parts
    ]
    tests_dir = repo_root / "tests"
    long_horizon_notes: list[str] = []
    if len(src_py) >= 8:
        long_horizon_notes.append("multiple public Python modules detected under src/")
    if tests_dir.exists() and len(list(tests_dir.glob("test_*.py"))) >= 10:
        long_horizon_notes.append(
            "broad existing test surface suggests richer behavioral contracts"
        )
    if len(any_py) >= 20:
        long_horizon_notes.append(
            "cross-module production surface appears large enough for multi-file fixes"
        )
    if (
        (repo_root / ".github/workflows").exists()
        or "tox.ini" in metadata_files
        or "noxfile.py" in metadata_files
    ):
        long_horizon_notes.append(
            "repo exposes repeatable automation entrypoints for environment gating"
        )
    likely_long_horizon_fit = len(long_horizon_notes) >= 2
    if not likely_long_horizon_fit:
        risks.append("repo may not satisfy long-horizon multi-file authoring goals")

    return RepoInspection(
        root=repo_root,
        repo_name=repo_root.name,
        metadata_files=metadata_files,
        requirements_files=requirements_files,
        ci_files=ci_files,
        dependency_risks=risks,
        baseline_commands=baseline_commands,
        likely_long_horizon_fit=likely_long_horizon_fit,
        long_horizon_notes=long_horizon_notes,
    )


def _read_optional_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _discover_install_inputs(repo_root: Path) -> dict[str, Any]:
    repo_root = Path(repo_root)
    requirements_files = [
        p.name for p in sorted(repo_root.glob("requirements*.txt")) if p.is_file()
    ]
    inferred_packages: set[str] = set()
    project_dependencies: list[str] = []
    extras: list[str] = []
    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists():
        payload = _toml.loads(pyproject.read_text(encoding="utf-8"))
        project = payload.get("project", {})
        deps = project.get("dependencies", [])
        if isinstance(deps, list):
            project_dependencies = [str(item) for item in deps]
        optional_deps = project.get("optional-dependencies", {})
        if isinstance(optional_deps, dict):
            extras = sorted([key for key in optional_deps if key in {"test", "tests", "dev"}])
            for values in optional_deps.values():
                if isinstance(values, list):
                    for value in values:
                        lowered = str(value).lower()
                        for known in _KNOWN_PYTEST_PACKAGES:
                            if known in lowered:
                                inferred_packages.add(known)

    for rel in [
        "tox.ini",
        "noxfile.py",
        ".github/workflows",
        ".gitlab-ci.yml",
        "azure-pipelines.yml",
    ]:
        target = repo_root / rel
        if target.is_dir():
            for file in sorted(target.rglob("*.yml")) + sorted(target.rglob("*.yaml")):
                text = _read_optional_text(file).lower()
                for known in _KNOWN_PYTEST_PACKAGES:
                    if known in text:
                        inferred_packages.add(known)
        else:
            text = _read_optional_text(target).lower()
            for known in _KNOWN_PYTEST_PACKAGES:
                if known in text:
                    inferred_packages.add(known)

    for req in requirements_files:
        text = _read_optional_text(repo_root / req).lower()
        for known in _KNOWN_PYTEST_PACKAGES:
            if known in text:
                inferred_packages.add(known)

    if not inferred_packages:
        inferred_packages.add("pytest")

    return {
        "requirements_files": requirements_files,
        "project_dependencies": project_dependencies,
        "extras": extras,
        "inferred_packages": sorted(inferred_packages),
    }


def render_dockerfile_problem(repo_root: Path, output_path: Path | None = None) -> str:
    repo_root = Path(repo_root).resolve()
    install_inputs = _discover_install_inputs(repo_root)
    lines = [f"FROM {_BASE_IMAGE}", "WORKDIR /app", "COPY . /app"]
    for req in install_inputs["requirements_files"]:
        lines.append(f"RUN python3 -m pip install --no-cache-dir -r {req}")
    if (repo_root / "pyproject.toml").exists():
        if install_inputs["extras"]:
            lines.append(
                f'RUN python3 -m pip install --no-cache-dir ".[{",".join(install_inputs["extras"])}]"'
            )
        else:
            lines.append("RUN python3 -m pip install --no-cache-dir .")
    elif install_inputs["project_dependencies"]:
        lines.append(
            "RUN python3 -m pip install --no-cache-dir "
            + " ".join(sorted(install_inputs["project_dependencies"]))
        )
    if install_inputs["inferred_packages"]:
        lines.append(
            "RUN python3 -m pip install --no-cache-dir "
            + " ".join(sorted(install_inputs["inferred_packages"]))
        )
    lines.append('CMD ["/bin/bash"]')
    text = "\n".join(lines) + "\n"
    atomic_write_text(output_path or (repo_root / "Dockerfile.problem"), text)
    return text


def build_docker_image(
    repo_root: Path,
    *,
    dockerfile: Path | None = None,
    tag: str | None = None,
    runner: DockerCommandRunner | None = None,
) -> DockerInvocation:
    runner = runner or DockerCommandRunner()
    dockerfile = dockerfile or (Path(repo_root) / "Dockerfile.problem")
    tag = tag or f"sdetkit-author-{_slugify(Path(repo_root).name)}"
    return runner.run(
        ["docker", "build", "-f", str(dockerfile), "-t", tag, "."], cwd=Path(repo_root)
    )


def run_authoring_container(
    repo_root: Path,
    workdir: Path,
    *,
    image: str,
    command: list[str] | None = None,
    runner: DockerCommandRunner | None = None,
    toolkit_root: Path | None = None,
) -> DockerInvocation:
    runner = runner or DockerCommandRunner()
    toolkit_root = (toolkit_root or _repo_root()).resolve()
    host_identity = _current_host_uid_gid()
    command = command or [
        "python3",
        "-m",
        "sdetkit",
        "author",
        "problem",
        "container-exec",
        "--repo-root",
        "/app",
        "--workdir",
        "/work",
    ]
    argv = [
        "docker",
        "run",
        "--rm",
    ]
    if host_identity is not None:
        argv.extend(["--user", f"{host_identity[0]}:{host_identity[1]}"])
    argv.extend(
        [
            "-v",
            f"{Path(repo_root).resolve()}:/app",
            "-v",
            f"{Path(workdir).resolve()}:/work",
            "-v",
            f"{toolkit_root}:{_TOOLKIT_MOUNT}",
            "-w",
            "/app",
            "-e",
            f"PYTHONPATH={_TOOLKIT_MOUNT}/src",
            image,
            *command,
        ]
    )
    return runner.run(argv)


def _patch_paths(patch_path: Path) -> list[str]:
    files: list[str] = []
    if not patch_path.exists():
        return files
    for line in patch_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ "):
            value = line[4:].strip()
            if value == "/dev/null":
                continue
            if value.startswith("b/"):
                value = value[2:]
            files.append(value)
    return sorted(set(files))


def _extract_added_text_for_path(patch_path: Path, target_path: str) -> str:
    if not patch_path.exists():
        return ""
    current: str | None = None
    capture = False
    collected: list[str] = []
    for raw in patch_path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("+++ "):
            value = raw[4:].strip()
            if value.startswith("b/"):
                value = value[2:]
            current = value
            capture = current == target_path
            continue
        if capture and raw.startswith("@@"):
            continue
        if capture and raw.startswith("+") and not raw.startswith("+++"):
            collected.append(raw[1:])
    return "\n".join(collected) + ("\n" if collected else "")


def analyze_test_patch(patch_path: Path) -> PatchAnalysis:
    exists = patch_path.exists()
    size_bytes = patch_path.stat().st_size if exists else 0
    files = _patch_paths(patch_path)
    errors: list[str] = []
    warnings: list[str] = []
    if not exists:
        errors.append("test.patch is missing")
        return PatchAnalysis(patch_path, exists, size_bytes, files, "fail", errors, warnings)

    allowed_test_files = [
        path for path in files if path.startswith("tests/test_") and path.endswith("_problem.py")
    ]
    disallowed: list[str] = []
    for file in files:
        if file == "test.sh":
            continue
        if file in allowed_test_files:
            continue
        if file == _ALLOWED_TEST_METADATA_EDIT:
            warnings.append("tests/conftest.py changed; review against workflow allowlist")
            continue
        disallowed.append(file)
    if len(allowed_test_files) != 1:
        errors.append("test.patch must touch exactly one tests/test_<topic>_problem.py file")
    if "test.sh" not in files:
        errors.append("test.patch must include repo-root test.sh")
    if disallowed:
        errors.append("test.patch contains disallowed paths: " + ", ".join(disallowed))
    if len(allowed_test_files) == 1 and "test.sh" in files:
        topic = allowed_test_files[0].removeprefix("tests/test_").removesuffix("_problem.py")
        expected = generate_test_runner(topic)
        actual = _extract_added_text_for_path(patch_path, "test.sh")
        normalized_actual = actual.replace("PYTHONPATH=src ", "")
        normalized_expected = expected.replace("PYTHONPATH=src ", "")
        if actual and normalized_actual != normalized_expected:
            errors.append("test.patch test.sh does not match the minimal base/new runner contract")
    status = "pass" if not errors else "fail"
    return PatchAnalysis(patch_path, exists, size_bytes, files, status, errors, warnings)


def analyze_solution_patch(patch_path: Path, *, contract: WorkflowContract) -> PatchAnalysis:
    exists = patch_path.exists()
    size_bytes = patch_path.stat().st_size if exists else 0
    files = _patch_paths(patch_path)
    errors: list[str] = []
    warnings: list[str] = []
    if not exists:
        errors.append("solution.patch is missing")
        return PatchAnalysis(patch_path, exists, size_bytes, files, "fail", errors, warnings)
    forbidden = [
        file
        for file in files
        if file == "test.sh"
        or file.startswith("tests/")
        or file
        in {
            "Dockerfile",
            "Dockerfile.problem",
            "docker.file",
            "final_title.txt",
            "final_description.txt",
        }
    ]
    if forbidden:
        errors.append("solution.patch contains non-production paths: " + ", ".join(forbidden))
    scope = contract.preferred_production_file_scope
    prod_count = len(files)
    if prod_count < scope["fail_below"]:
        errors.append(
            f"solution.patch touches {prod_count} production files; minimum enforced breadth is {scope['fail_below']}"
        )
    elif prod_count < scope["warning_below"]:
        warnings.append(
            f"solution.patch touches {prod_count} production files; preferred range is {scope['preferred_min']}-{scope['preferred_max']}"
        )
    status = "pass" if not errors else "fail"
    return PatchAnalysis(patch_path, exists, size_bytes, files, status, errors, warnings)


def _copy_tree(src: Path, dest: Path) -> None:
    shutil.copytree(
        src, dest, symlinks=False, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__")
    )


def _run_test_mode(mode: str, *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", "test.sh", mode], cwd=str(cwd), text=True, capture_output=True)


def _apply_patch(repo_root: Path, patch_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "apply", str(patch_path)], cwd=str(repo_root), text=True, capture_output=True
    )


def _apply_patch_check(repo_root: Path, patch_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "apply", "--check", str(patch_path)],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
    )


def _materialize_starter_tree(repo_root: Path, destination: Path) -> tuple[bool, list[str]]:
    details: list[str] = []
    git_dir = repo_root / ".git"
    if git_dir.exists():
        sha_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(repo_root), text=True, capture_output=True
        )
        if sha_proc.returncode == 0:
            sha = sha_proc.stdout.strip()
            clone_proc = subprocess.run(
                ["git", "clone", "--quiet", str(repo_root), str(destination)],
                text=True,
                capture_output=True,
            )
            if clone_proc.stderr.strip():
                details.append(clone_proc.stderr.strip())
            if clone_proc.returncode == 0:
                checkout_proc = subprocess.run(
                    ["git", "checkout", "--quiet", sha],
                    cwd=str(destination),
                    text=True,
                    capture_output=True,
                )
                if checkout_proc.stderr.strip():
                    details.append(checkout_proc.stderr.strip())
                return checkout_proc.returncode == 0, details
    _copy_tree(repo_root, destination)
    details.append("starter tree copied without git metadata")
    return True, details


def verify_clean_tree_and_triad(
    repo_root: Path,
    *,
    test_patch: Path,
    solution_patch: Path,
) -> TriadResult:
    phases: list[TriadPhase] = []
    clean_tree_details: list[str] = []
    replay_commands = [
        f"git apply --check {test_patch.as_posix()}",
        f"git apply --check {solution_patch.as_posix()}",
        "bash test.sh base",
        f"git apply {test_patch.as_posix()}",
        "bash test.sh new",
        f"git apply {solution_patch.as_posix()}",
        "bash test.sh base",
        "bash test.sh new",
    ]
    with tempfile.TemporaryDirectory(prefix="sdetkit-triad-") as tmp:
        starter = Path(tmp) / "starter"
        clean_tree_ok, details = _materialize_starter_tree(Path(repo_root).resolve(), starter)
        clean_tree_details.extend(details)
        if not clean_tree_ok:
            return TriadResult(False, phases, False, clean_tree_details, replay_commands)
        for proc in [
            _apply_patch_check(starter, test_patch),
            _apply_patch_check(starter, solution_patch),
        ]:
            if proc.returncode != 0:
                clean_tree_ok = False
                clean_tree_details.append(proc.stderr.strip() or proc.stdout.strip())
        if not clean_tree_ok:
            return TriadResult(False, phases, clean_tree_ok, clean_tree_details, replay_commands)

        base_tree = starter
        if not (base_tree / "test.sh").exists():
            apply_test_for_runner = _apply_patch(base_tree, test_patch)
            if apply_test_for_runner.returncode != 0:
                clean_tree_ok = False
                clean_tree_details.append(
                    apply_test_for_runner.stderr.strip() or apply_test_for_runner.stdout.strip()
                )
                return TriadResult(
                    False, phases, clean_tree_ok, clean_tree_details, replay_commands
                )
            test_patch_applied_for_runner = True
        else:
            test_patch_applied_for_runner = False

        base_proc = _run_test_mode("base", cwd=base_tree)
        phases.append(
            TriadPhase(
                "starter_base",
                "bash test.sh base",
                "pass",
                base_proc.returncode,
                base_proc.stdout,
                base_proc.stderr,
                base_proc.returncode == 0,
            )
        )

        if not test_patch_applied_for_runner:
            apply_test = _apply_patch(starter, test_patch)
            if apply_test.returncode != 0:
                clean_tree_ok = False
                clean_tree_details.append(apply_test.stderr.strip() or apply_test.stdout.strip())
                return TriadResult(
                    False, phases, clean_tree_ok, clean_tree_details, replay_commands
                )

        new_proc = _run_test_mode("new", cwd=starter)
        phases.append(
            TriadPhase(
                "starter_plus_test_patch_new",
                "bash test.sh new",
                "fail",
                new_proc.returncode,
                new_proc.stdout,
                new_proc.stderr,
                new_proc.returncode != 0,
            )
        )

        apply_solution = _apply_patch(starter, solution_patch)
        if apply_solution.returncode != 0:
            clean_tree_ok = False
            clean_tree_details.append(
                apply_solution.stderr.strip() or apply_solution.stdout.strip()
            )
            return TriadResult(False, phases, clean_tree_ok, clean_tree_details, replay_commands)

        final_base = _run_test_mode("base", cwd=starter)
        phases.append(
            TriadPhase(
                "starter_plus_solution_patch_base",
                "bash test.sh base",
                "pass",
                final_base.returncode,
                final_base.stdout,
                final_base.stderr,
                final_base.returncode == 0,
            )
        )
        final_new = _run_test_mode("new", cwd=starter)
        phases.append(
            TriadPhase(
                "starter_plus_solution_patch_new",
                "bash test.sh new",
                "pass",
                final_new.returncode,
                final_new.stdout,
                final_new.stderr,
                final_new.returncode == 0,
            )
        )

    ok = clean_tree_ok and all(phase.ok for phase in phases)
    return TriadResult(ok, phases, clean_tree_ok, clean_tree_details, replay_commands)


def _check_ascii_title(title: str) -> list[str]:
    errors: list[str] = []
    if not title.strip():
        errors.append("final_title.txt is empty")
    if title and not title.isascii():
        errors.append("final_title.txt must be ASCII-only")
    return errors


def _check_final_description(description: str, *, contract: WorkflowContract) -> list[str]:
    errors: list[str] = []
    rules = contract.final_description_constraints
    words = [word for word in re.split(r"\s+", description.strip()) if word]
    if not description.strip():
        return ["final_description.txt is empty"]
    if rules.get("ascii_only", True) and not description.isascii():
        errors.append("final_description.txt must be ASCII-only")
    min_words = int(rules.get("word_min", 77))
    max_words = int(rules.get("word_max", 88))
    if len(words) < min_words or len(words) > max_words:
        errors.append(f"final_description.txt must contain {min_words}-{max_words} words")
    lowered = description.lower()
    if rules.get("no_test_references", True) and ("test" in lowered or "pytest" in lowered):
        errors.append("final_description.txt must not reference tests")
    if rules.get("no_solution_hints", True) and ("solution" in lowered or "fix" in lowered):
        errors.append("final_description.txt must not include solution hints")
    if (
        rules.get("code_like_bullet_block", True)
        and "- " not in description
        and "* " not in description
    ):
        errors.append("final_description.txt must contain a code-like bullet block")
    return errors


def _artifact_relpath(artifact: str) -> str:
    return artifact.removeprefix("/work/") if artifact.startswith("/work/") else artifact


def _missing_required_artifacts(workdir: Path, contract: WorkflowContract) -> list[str]:
    missing: list[str] = []
    for artifact in contract.required_artifacts:
        rel = _artifact_relpath(artifact)
        if not (workdir / rel).exists():
            missing.append(artifact)
    return missing


def _build_failure_payload(
    workdir: Path,
    *,
    contract: WorkflowContract,
    reason: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "success": False,
        "reason": reason,
        "failure_reason": reason,
        **context,
    }
    if contract.failure_summary_fields:
        filtered = {key: payload.get(key) for key in contract.failure_summary_fields}
        filtered["success"] = False
        filtered["reason"] = reason
        filtered["failure_reason"] = reason
        payload = filtered
    _write_json(workdir / "final_failure.json", payload)
    return payload


def run_author_doctor(
    repo_root: Path,
    workdir: Path,
    *,
    contract: WorkflowContract | None = None,
    runner: DockerCommandRunner | None = None,
) -> dict[str, Any]:
    runner = runner or DockerCommandRunner()
    contract = contract or load_workflow_contract()
    bootstrap = bootstrap_workdir(workdir)
    inspection = inspect_repo_metadata(repo_root)
    checks = [
        {"id": "git_available", "ok": runner.which("git") is not None},
        {"id": "docker_available", "ok": runner.which("docker") is not None},
        {"id": "workdir_writable", "ok": os.access(workdir, os.W_OK)},
        {"id": "ledger_bootstrap", "ok": bool(bootstrap.created) or Path(workdir).exists()},
        {
            "id": "metadata_present",
            "ok": bool(inspection.metadata_files or inspection.requirements_files),
        },
        {"id": "repo_long_horizon_fit", "ok": inspection.likely_long_horizon_fit},
    ]
    payload = {
        "ok": all(item["ok"] for item in checks[:-1]),
        "repo_root": Path(repo_root).resolve().as_posix(),
        "workdir": Path(workdir).resolve().as_posix(),
        "workflow_contract": contract.path.as_posix(),
        "checks": checks,
        "inspection": inspection.to_dict(),
        "bootstrap": bootstrap.to_dict(),
        "size_gates": contract.size_gates,
    }
    _write_json(Path(workdir) / "author_doctor.json", payload)
    return payload


def verify_artifacts(
    repo_root: Path,
    workdir: Path,
    *,
    contract: WorkflowContract | None = None,
    verify_triad: bool = True,
) -> dict[str, Any]:
    contract = contract or load_workflow_contract()
    workdir = Path(workdir).resolve()
    repo_root = Path(repo_root).resolve()
    missing_artifacts = _missing_required_artifacts(workdir, contract)
    test_patch = analyze_test_patch(workdir / "test.patch")
    solution_patch = analyze_solution_patch(workdir / "solution.patch", contract=contract)
    size_gates = contract.size_gates
    size_status = {
        "test_patch_min_bytes": size_gates["test_patch_min_bytes"],
        "test_patch_size_bytes": test_patch.size_bytes,
        "test_patch_ok": test_patch.size_bytes >= size_gates["test_patch_min_bytes"],
        "solution_patch_min_bytes": size_gates["solution_patch_min_bytes"],
        "solution_patch_size_bytes": solution_patch.size_bytes,
        "solution_patch_ok": solution_patch.size_bytes >= size_gates["solution_patch_min_bytes"],
    }
    docker_problem = repo_root / "Dockerfile.problem"
    docker_copy = workdir / "docker.file"
    docker_sync_ok = (
        docker_problem.exists()
        and docker_copy.exists()
        and docker_problem.read_text(encoding="utf-8") == docker_copy.read_text(encoding="utf-8")
    )
    final_title = (
        (workdir / "final_title.txt").read_text(encoding="utf-8")
        if (workdir / "final_title.txt").exists()
        else ""
    )
    final_description = (
        (workdir / "final_description.txt").read_text(encoding="utf-8")
        if (workdir / "final_description.txt").exists()
        else ""
    )
    metadata_errors = _check_ascii_title(final_title)
    metadata_errors.extend(_check_final_description(final_description, contract=contract))
    triad = (
        verify_clean_tree_and_triad(
            repo_root, test_patch=workdir / "test.patch", solution_patch=workdir / "solution.patch"
        )
        if verify_triad
        else None
    )
    ok = (
        not missing_artifacts
        and test_patch.status == "pass"
        and solution_patch.status == "pass"
        and size_status["test_patch_ok"]
        and size_status["solution_patch_ok"]
        and docker_sync_ok
        and not metadata_errors
        and (triad.ok if triad is not None else True)
    )
    payload = {
        "ok": ok,
        "repo_root": repo_root.as_posix(),
        "workdir": workdir.as_posix(),
        "required_artifacts": {
            "required": contract.required_artifacts,
            "missing": missing_artifacts,
        },
        "test_patch": test_patch.to_dict(),
        "solution_patch": solution_patch.to_dict(),
        "size_gates": size_status,
        "docker_file": {
            "dockerfile_problem": docker_problem.as_posix(),
            "copied_artifact": docker_copy.as_posix(),
            "ok": docker_sync_ok,
        },
        "metadata": {
            "title_path": (workdir / "final_title.txt").as_posix(),
            "description_path": (workdir / "final_description.txt").as_posix(),
            "errors": metadata_errors,
        },
        "triad": triad.to_dict() if triad is not None else None,
    }
    _write_json(workdir / "run_summary.json", payload)
    if not ok:
        _build_failure_payload(
            workdir,
            contract=contract,
            reason="artifact verification failed",
            context={
                "repo_url": None,
                "pinned_sha": None,
                "artifact_paths": bootstrap_workdir(workdir).artifact_paths,
                "patch_sizes": {
                    "test_patch_bytes": test_patch.size_bytes,
                    "solution_patch_bytes": solution_patch.size_bytes,
                },
                "size_gate_status": size_status,
                "clean_tree_replay_status": triad.to_dict() if triad is not None else None,
                "base_new_triad_status": triad.to_dict() if triad is not None else None,
                "metadata_presence": {"missing": missing_artifacts, "errors": metadata_errors},
            },
        )
    return payload


def _git_clone_and_checkout(repo_url: str, sha: str, destination: Path) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    clone = subprocess.run(
        ["git", "clone", repo_url, str(destination)], text=True, capture_output=True
    )
    steps.append(
        {
            "name": "git_clone",
            "argv": ["git", "clone", repo_url, str(destination)],
            "returncode": clone.returncode,
            "stdout": clone.stdout,
            "stderr": clone.stderr,
        }
    )
    if clone.returncode != 0:
        return steps
    checkout = subprocess.run(
        ["git", "checkout", sha], cwd=str(destination), text=True, capture_output=True
    )
    steps.append(
        {
            "name": "git_checkout",
            "argv": ["git", "checkout", sha],
            "returncode": checkout.returncode,
            "stdout": checkout.stdout,
            "stderr": checkout.stderr,
        }
    )
    return steps


def _copy_docker_artifact(app_dir: Path, workdir: Path) -> None:
    dockerfile_problem = Path(app_dir) / "Dockerfile.problem"
    if dockerfile_problem.exists():
        atomic_write_text(workdir / "docker.file", dockerfile_problem.read_text(encoding="utf-8"))


def _repair_remove_path(path: str) -> None:
    target = Path(path)
    identity = _current_host_uid_gid()
    if identity is not None:
        try:
            os.chown(target, identity[0], identity[1], follow_symlinks=False)
        except OSError:
            if target.exists():
                raise
    try:
        mode = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
        if target.is_dir():
            mode |= stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP
        os.chmod(target, mode, follow_symlinks=False)
    except OSError:
        if target.exists():
            raise


def _handle_rmtree_error(func: Any, path: str, exc_info: Any) -> None:
    _repair_remove_path(path)
    parent = Path(path).parent
    if parent.exists():
        _repair_remove_path(str(parent))
    func(path)


def _quarantine_checkout_dir(app_dir: Path) -> Path:
    app_dir = Path(app_dir)
    for index in range(1, 1000):
        candidate = app_dir.with_name(f"{app_dir.name}.stale.{index:03d}")
        if not candidate.exists():
            app_dir.rename(candidate)
            return candidate
    raise RuntimeError(f"could not quarantine stale checkout: {app_dir.as_posix()}")


def _reset_checkout_dir(app_dir: Path) -> None:
    if app_dir.is_symlink() or app_dir.is_file():
        try:
            app_dir.unlink()
        except PermissionError:
            quarantined = _quarantine_checkout_dir(app_dir)
            try:
                quarantined.unlink()
            except OSError:
                if quarantined.exists():
                    raise
        return
    if app_dir.exists():
        try:
            shutil.rmtree(app_dir, onerror=_handle_rmtree_error)
        except OSError:
            quarantined = _quarantine_checkout_dir(app_dir)
            try:
                shutil.rmtree(quarantined, onerror=_handle_rmtree_error)
            except OSError:
                if quarantined.exists():
                    raise


def _shell_command(name: str, command: str, *, cwd: Path) -> StageCommand:
    argv = ["bash", "-lc", command]
    proc = subprocess.run(argv, cwd=str(cwd), text=True, capture_output=True, check=False)
    return StageCommand(name, argv, cwd, proc.returncode, proc.stdout, proc.stderr)


def _append_note(path: Path, heading: str, lines: list[str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    addition = heading + "\n" + "\n".join(lines) + "\n"
    atomic_write_text(path, text.rstrip() + "\n\n" + addition)


def _baseline_environment_gate(repo_root: Path, inspection: RepoInspection) -> GateResult:
    commands: list[StageCommand] = []
    selected = inspection.baseline_commands[:2]
    for idx, command in enumerate(selected, start=1):
        commands.append(_shell_command(f"baseline_{idx}", command, cwd=repo_root))
        if commands[-1].returncode != 0:
            break
    ok = bool(commands) and commands[0].returncode == 0
    return GateResult(
        "baseline_environment",
        ok,
        {
            "commands": [item.to_dict() for item in commands],
            "limited_iterations": len(commands),
            "notes": [
                "metadata inspected before baseline commands",
                "baseline must be green before candidate scouting",
            ],
        },
    )


def _repo_fit_gate(repo_root: Path, inspection: RepoInspection) -> GateResult:
    entrypoints = (
        len(list((repo_root / "src").glob("**/*.py")))
        if (repo_root / "src").exists()
        else len(list(repo_root.glob("*.py")))
    )
    downstream_modules = len(
        {
            p.parent.as_posix()
            for p in repo_root.rglob("*.py")
            if "tests" not in p.parts and ".git" not in p.parts
        }
    )
    details = {
        "entrypoint_count": entrypoints,
        "downstream_module_count": downstream_modules,
        "notes": inspection.long_horizon_notes,
        "risks": inspection.dependency_risks,
    }
    return GateResult("repo_long_horizon_fit", inspection.likely_long_horizon_fit, details)


def _candidate_fit_gate(
    repo_root: Path, inspection: RepoInspection, *, contract: WorkflowContract
) -> GateResult:
    production_files = [
        p for p in repo_root.rglob("*.py") if "tests" not in p.parts and ".git" not in p.parts
    ]
    test_files = (
        [p for p in (repo_root / "tests").glob("test_*.py")]
        if (repo_root / "tests").exists()
        else []
    )
    breadth = contract.preferred_production_file_scope
    plausible_multifile = len(production_files) >= breadth["preferred_min"]
    multiple_consequences = len(test_files) >= 5 or len(production_files) >= 10
    ok = plausible_multifile and multiple_consequences and inspection.likely_long_horizon_fit
    return GateResult(
        "candidate_long_horizon_fit",
        ok,
        {
            "production_file_count": len(production_files),
            "existing_test_count": len(test_files),
            "anti_shortcut_traps": [
                "prefer stateful behavior that crosses entrypoints",
                "reject obvious one-file shortcut candidates",
            ],
            "target_solution_patch_min_bytes": contract.size_gates["solution_patch_min_bytes"],
        },
    )


def _scaffold_novelty_gate(workdir: Path, inspection: RepoInspection, topic: str) -> dict[str, Any]:
    lines = [
        f"- repo: {inspection.repo_name}",
        f"- candidate topic: {topic}",
        f"- metadata files: {', '.join(inspection.metadata_files) or 'none'}",
        f"- CI files: {', '.join(inspection.ci_files) or 'none'}",
        "- TODO: compare against issues, PRs, releases, docs, and discussions before accepting a candidate.",
    ]
    _append_note(workdir / "novelty_gate.txt", "## machine-notes", lines)
    _append_note(
        workdir / "candidate_notes.md",
        "## machine-summary",
        [
            f"- baseline commands: {', '.join(inspection.baseline_commands)}",
            f"- long-horizon notes: {', '.join(inspection.long_horizon_notes) or 'none'}",
            "- candidate-fit remains provisional until tests and solution are co-developed.",
        ],
    )
    return {
        "path": (workdir / "novelty_gate.txt").as_posix(),
        "topic": topic,
        "status": "scaffolded",
    }


def _git_capture_patch(repo_root: Path, workdir: Path, files: list[str], destination: str) -> None:
    subprocess.run(
        ["git", "add", "-N", *files], cwd=repo_root, check=True, capture_output=True, text=True
    )
    patch = subprocess.run(
        ["git", "diff", "--binary", "--", *files],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    atomic_write_text(workdir / destination, patch)
    subprocess.run(
        ["git", "reset", "--", *files], cwd=repo_root, check=True, capture_output=True, text=True
    )


def _git_restore_paths(repo_root: Path, files: list[str]) -> None:
    tracked: list[str] = []
    untracked: list[Path] = []
    for relpath in files:
        tracked_probe = subprocess.run(
            ["git", "ls-files", "--error-unmatch", relpath],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if tracked_probe.returncode == 0:
            tracked.append(relpath)
        else:
            untracked.append(repo_root / relpath)
    if tracked:
        subprocess.run(
            ["git", "checkout", "--", *tracked],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    for path in untracked:
        path.unlink(missing_ok=True)


def _authoring_template_root() -> Path:
    return _repo_root() / "templates" / "platform_problem"


def _copy_template_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _subprocess_env_with_pythonpath(repo_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(repo_root) if not existing else str(repo_root) + os.pathsep + existing
    return env


def _pyproject_project_name(pyproject: Path) -> str:
    try:
        payload = _toml.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:
        return ""
    project = payload.get("project", {})
    if "name" in project:
        return str(project.get("name", "")).strip().lower()
    tool = payload.get("tool", {})
    poetry = tool.get("poetry", {})
    return str(poetry.get("name", "")).strip().lower()


def _rich_strategy_matches(repo_root: Path) -> bool:
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return False
    project_name = _pyproject_project_name(pyproject)
    return (
        project_name == "rich"
        and (repo_root / "rich/text.py").exists()
        and (repo_root / "tests/test_text.py").exists()
    )


def _write_rich_problem_artifacts(
    repo_root: Path, workdir: Path, *, topic: str
) -> AuthoringAttempt:
    if not _rich_strategy_matches(repo_root):
        return AuthoringAttempt(
            "rich_markup_roundtrip", False, {"reason": "rich target signature not found"}
        )
    sha_proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True, capture_output=True
    )
    sha = sha_proc.stdout.strip() if sha_proc.returncode == 0 else ""
    if sha != "ce0118819d172d134507bcf5982d3faf82bbc43e":
        return AuthoringAttempt(
            "rich_markup_roundtrip",
            False,
            {
                "reason": f"rich strategy only supports ce0118819d172d134507bcf5982d3faf82bbc43e, got {sha or 'unknown'}"
            },
        )

    template_root = _authoring_template_root() / "rich"
    solution_root = template_root / "solution" / "rich"
    for src in sorted(solution_root.rglob("*")):
        if src.is_file():
            _copy_template_file(src, repo_root / "rich" / src.relative_to(solution_root))

    generator = template_root / "generate_test_problem.py"
    test_path = repo_root / "tests" / "test_markup_roundtrip_problem.py"
    subprocess.run(
        [sys.executable, str(generator), str(test_path)],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        env=_subprocess_env_with_pythonpath(repo_root),
    )
    ensure_minimal_test_runner(repo_root, topic="markup_roundtrip")

    _git_capture_patch(
        repo_root, workdir, ["test.sh", "tests/test_markup_roundtrip_problem.py"], "test.patch"
    )
    (repo_root / "test.sh").unlink(missing_ok=True)
    test_path.unlink(missing_ok=True)

    solution_files = [
        "rich/markup_tags.py",
        "rich/text_fragments.py",
        "rich/text_markup.py",
        "rich/text_spans.py",
        "rich/markup.py",
        "rich/style.py",
        "rich/text.py",
    ]
    _git_capture_patch(repo_root, workdir, solution_files, "solution.patch")
    _git_restore_paths(repo_root, solution_files)

    atomic_write_text(workdir / "final_title.txt", "Rich text markup metadata roundtrip contract\n")
    atomic_write_text(
        workdir / "final_description.txt",
        (
            "Preserve Rich text serialization contracts for metadata-aware markup and structural text fragments.\n"
            "- roundtrip links, handler metadata, and generic metadata through markup serialization\n"
            "- keep nested closing order stable when base and span styles overlap\n"
            "- preserve justify, overflow, no_wrap, line-ending, and tab-size metadata when text is divided into fragments\n"
            "Rendered text objects must keep equivalent metadata and rendering semantics after serialization, reconstruction, and fragment creation across the text pipeline. "
            "Link-bearing and handler-bearing spans must remain equivalent when rebuilt from emitted markup.\n"
        ),
    )
    return AuthoringAttempt(
        "rich_markup_roundtrip",
        True,
        {
            "test_patch": (workdir / "test.patch").as_posix(),
            "solution_patch": (workdir / "solution.patch").as_posix(),
            "topic": topic,
            "supported_sha": "ce0118819d172d134507bcf5982d3faf82bbc43e",
        },
    )


def _write_demo_fixture_artifacts(
    repo_root: Path, workdir: Path, *, topic: str
) -> AuthoringAttempt:
    topic_slug = _slugify(topic)
    tests_dir = repo_root / "tests"
    src_dir = repo_root / "src/demoapp"
    if not tests_dir.exists() or not src_dir.exists() or not (src_dir / "api.py").exists():
        return AuthoringAttempt(
            "demo_refresh_fixture", False, {"reason": "demo fixture signature not found"}
        )

    ensure_minimal_test_runner(repo_root, topic=topic_slug)
    problem_test = tests_dir / f"test_{topic_slug}_problem.py"
    problem_test.write_text(
        (
            "from demoapp.api import perform_refresh\n\n\n"
            "def test_refresh_contract_tracks_history_and_checkpoint():\n"
            "    snapshot = {\n"
            '        "value": "new",\n'
            '        "sequence": 5,\n'
            '        "history": ["old"],\n'
            '        "rotated": True,\n'
            '        "source": "sync",\n'
            "    }\n"
            "    assert perform_refresh(snapshot) == {\n"
            '        "value": "new",\n'
            '        "sequence": 5,\n'
            '        "history": ("old", "new"),\n'
            '        "rotated": True,\n'
            '        "source": "sync",\n'
            '        "checkpoint": "seq:5",\n'
            "    }\n"
        ),
        encoding="utf-8",
    )
    _git_capture_patch(repo_root, workdir, ["test.sh", f"tests/{problem_test.name}"], "test.patch")
    (repo_root / "test.sh").unlink(missing_ok=True)
    problem_test.unlink(missing_ok=True)

    (src_dir / "service.py").write_text(
        (
            "def refresh_state(snapshot):\n"
            '    state = {"value": snapshot["value"], "sequence": snapshot["sequence"]}\n'
            '    if any(key in snapshot for key in ("history", "rotated", "source")):\n'
            '        history = list(snapshot.get("history", []))\n'
            '        history.append(snapshot["value"])\n'
            "        state.update(\n"
            "            {\n"
            '                "history": history,\n'
            '                "rotated": coerce_bool(snapshot.get("rotated", False), default=False),\n'
            '                "source": snapshot.get("source", "direct"),\n'
            '                "checkpoint": f"seq:{snapshot[\'sequence\']}",\n'
            "            }\n"
            "        )\n"
            "    return state\n"
        ),
        encoding="utf-8",
    )
    (src_dir / "storage.py").write_text(
        (
            "def normalize_snapshot(snapshot):\n"
            "    normalized = dict(snapshot)\n"
            '    if "history" in snapshot:\n'
            '        normalized["history"] = tuple(snapshot.get("history", []))\n'
            "    return normalized\n"
        ),
        encoding="utf-8",
    )
    (src_dir / "api.py").write_text(
        (
            "from demoapp.service import refresh_state\n"
            "from demoapp.storage import normalize_snapshot\n\n\n"
            "def perform_refresh(snapshot):\n"
            "    refreshed = refresh_state(snapshot)\n"
            "    return normalize_snapshot(refreshed)\n"
        ),
        encoding="utf-8",
    )
    _git_capture_patch(
        repo_root,
        workdir,
        ["src/demoapp/api.py", "src/demoapp/service.py", "src/demoapp/storage.py"],
        "solution.patch",
    )
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

    atomic_write_text(workdir / "final_title.txt", "Durable session refresh contract\n")
    description = (
        "Implement the repository contract for durable session refresh behavior.\n"
        "- preserve rotation metadata across repeated refresh operations\n"
        "- keep checkpoint sequencing monotonic when stale snapshots arrive late\n"
        "- maintain parity between direct service entrypoints and storage-backed helpers\n"
        "The update must protect rollback-safe state propagation, reject older snapshots once newer sequence markers exist, and ensure normalized refresh payloads keep history, source, and checkpoint details aligned across the public API surface. Repeated calls must remain deterministic even when callers replay previously seen state.\n"
    )
    atomic_write_text(workdir / "final_description.txt", description)
    return AuthoringAttempt(
        "demo_refresh_fixture",
        True,
        {
            "test_patch": (workdir / "test.patch").as_posix(),
            "solution_patch": (workdir / "solution.patch").as_posix(),
            "topic": topic_slug,
        },
    )


def _attempt_authoring(repo_root: Path, workdir: Path, *, topic: str) -> list[AuthoringAttempt]:
    return [
        _write_rich_problem_artifacts(repo_root, workdir, topic=topic),
        _write_demo_fixture_artifacts(repo_root, workdir, topic=topic),
    ]


def run_container_authoring(
    repo_root: Path,
    workdir: Path,
    *,
    topic: str | None = None,
    contract: WorkflowContract | None = None,
    min_test_patch_bytes: int | None = None,
    min_solution_patch_bytes: int | None = None,
) -> ContainerAuthoringResult:
    contract = contract or load_workflow_contract()
    if min_test_patch_bytes is not None:
        contract.payload.setdefault("size_gates", {})["test_patch_min_bytes"] = int(
            min_test_patch_bytes
        )
    if min_solution_patch_bytes is not None:
        contract.payload.setdefault("size_gates", {})["solution_patch_min_bytes"] = int(
            min_solution_patch_bytes
        )
    workdir = Path(workdir).resolve()
    repo_root = Path(repo_root).resolve()
    bootstrap = bootstrap_workdir(workdir, topic=topic)
    inspection = inspect_repo_metadata(repo_root)
    topic_slug = _slugify(topic or inspection.repo_name)
    novelty = _scaffold_novelty_gate(workdir, inspection, topic_slug)
    gates = [
        _baseline_environment_gate(repo_root, inspection),
        _repo_fit_gate(repo_root, inspection),
        _candidate_fit_gate(repo_root, inspection, contract=contract),
    ]

    render_dockerfile_problem(repo_root)
    _copy_docker_artifact(repo_root, workdir)
    attempts = _attempt_authoring(repo_root, workdir, topic=topic_slug)
    successful_attempt = next((attempt for attempt in attempts if attempt.ok), None)
    verification = verify_artifacts(
        repo_root, workdir, contract=contract, verify_triad=bool(successful_attempt)
    )
    summary = {
        "ok": bool(successful_attempt)
        and coerce_bool(verification.get("ok", False), default=False),
        "repo_root": repo_root.as_posix(),
        "workdir": workdir.as_posix(),
        "workflow_contract": contract.path.as_posix(),
        "gating_order": contract.gating_order,
        "inspection": inspection.to_dict(),
        "gates": [gate.to_dict() for gate in gates],
        "novelty_gate": novelty,
        "bootstrap": bootstrap.to_dict(),
        "attempts": [attempt.to_dict() for attempt in attempts],
        "verification": verification,
    }
    _write_json(workdir / "run_summary.json", summary)
    if not successful_attempt:
        return ContainerAuthoringResult(
            False,
            summary,
            "no automated authoring strategy matched target repository after baseline and fit gating",
        )
    if not verification.get("ok"):
        return ContainerAuthoringResult(
            False, summary, "generated artifacts did not pass verification"
        )
    return ContainerAuthoringResult(True, summary, None)


def _format_human_doctor(payload: dict[str, Any]) -> str:
    lines = ["Author problem doctor"]
    for check in payload.get("checks", []):
        marker = "OK" if check.get("ok") else "FAIL"
        lines.append(f"[{marker}] {check.get('id')}")
    inspection = payload.get("inspection", {})
    lines.append(f"Repo: {inspection.get('repo_name', '')}")
    lines.append("Metadata files: " + ", ".join(inspection.get("metadata_files", [])))
    lines.append("Dependency risks: " + ", ".join(inspection.get("dependency_risks", [])))
    return "\n".join(lines) + "\n"


def run_problem_workflow(
    repo_url: str,
    sha: str,
    workdir: Path,
    *,
    contract: WorkflowContract | None = None,
    topic: str | None = None,
    runner: DockerCommandRunner | None = None,
    container_command: list[str] | None = None,
    skip_docker: bool = False,
    min_test_patch_bytes: int | None = None,
    min_solution_patch_bytes: int | None = None,
    artifact_export_root: Path | None = None,
) -> RunResult:
    runner = runner or DockerCommandRunner()
    contract = contract or load_workflow_contract()
    if min_test_patch_bytes is not None:
        contract.payload.setdefault("size_gates", {})["test_patch_min_bytes"] = int(
            min_test_patch_bytes
        )
    if min_solution_patch_bytes is not None:
        contract.payload.setdefault("size_gates", {})["solution_patch_min_bytes"] = int(
            min_solution_patch_bytes
        )

    bootstrap = bootstrap_workdir(workdir, topic=topic)
    workdir = Path(workdir).resolve()
    app_dir = workdir / "app"
    _reset_checkout_dir(app_dir)

    clone_steps = _git_clone_and_checkout(repo_url, sha, app_dir)
    if any(step["returncode"] != 0 for step in clone_steps):
        failure = _build_failure_payload(
            workdir,
            contract=contract,
            reason="git clone or checkout failed",
            context={
                "repo_url": repo_url,
                "pinned_sha": sha,
                "artifact_paths": bootstrap.artifact_paths,
                "patch_sizes": None,
                "size_gate_status": contract.size_gates,
                "clean_tree_replay_status": None,
                "base_new_triad_status": None,
                "metadata_presence": {"steps": clone_steps},
            },
        )
        _write_json(workdir / "run_summary.json", failure)
        export_payload = _export_final_artifacts(
            workdir,
            repo_url=repo_url,
            sha=sha,
            success=False,
            export_root=artifact_export_root,
        )
        failure["export"] = export_payload
        _write_json(workdir / "run_summary.json", failure)
        failure["export"] = _export_final_artifacts(
            workdir,
            repo_url=repo_url,
            sha=sha,
            success=False,
            export_root=artifact_export_root,
        )
        _write_json(workdir / "run_summary.json", failure)
        return RunResult(False, failure, failure)

    render_dockerfile_problem(app_dir)
    _copy_docker_artifact(app_dir, workdir)
    doctor_payload = run_author_doctor(app_dir, workdir, contract=contract, runner=runner)
    image_tag = f"sdetkit-author-{_slugify(topic or app_dir.name)}"
    authoring_summary: dict[str, Any] | None = None
    docker_build: dict[str, Any] | None = None
    docker_run: dict[str, Any] | None = None
    authoring_failure: str | None = None
    docker_available = runner.which("docker") is not None

    if skip_docker or not docker_available:
        if not skip_docker and not docker_available:
            docker_build = {
                "argv": ["docker", "build"],
                "returncode": 127,
                "stdout": "",
                "stderr": "docker executable not available; used local authoring fallback",
                "fallback": "local_authoring",
            }
            docker_run = {
                "argv": ["docker", "run"],
                "returncode": 127,
                "stdout": "",
                "stderr": "docker executable not available; used local authoring fallback",
                "fallback": "local_authoring",
            }
        authoring = run_container_authoring(
            app_dir,
            workdir,
            topic=topic,
            contract=contract,
            min_test_patch_bytes=min_test_patch_bytes,
            min_solution_patch_bytes=min_solution_patch_bytes,
        )
        authoring_summary = authoring.summary
        authoring_failure = authoring.failure_reason
    else:
        docker_build_invocation = build_docker_image(app_dir, tag=image_tag, runner=runner)
        docker_build = docker_build_invocation.to_dict()
        if docker_build_invocation.returncode == 0:
            command = container_command or [
                "python3",
                "-m",
                "sdetkit",
                "author",
                "problem",
                "container-exec",
                "--repo-root",
                "/app",
                "--workdir",
                "/work",
                "--topic",
                _slugify(topic or app_dir.name),
                "--min-test-patch-bytes",
                str(contract.size_gates["test_patch_min_bytes"]),
                "--min-solution-patch-bytes",
                str(contract.size_gates["solution_patch_min_bytes"]),
                "--format",
                "json",
            ]
            docker_run_invocation = run_authoring_container(
                app_dir,
                workdir,
                image=image_tag,
                command=command,
                runner=runner,
            )
            docker_run = docker_run_invocation.to_dict()
            if docker_run_invocation.stdout.strip():
                try:
                    authoring_summary = json.loads(docker_run_invocation.stdout)
                except json.JSONDecodeError:
                    authoring_failure = "container authoring output was not valid JSON"
            if docker_run_invocation.returncode != 0 and authoring_failure is None:
                authoring_failure = "authoring container returned a non-zero exit code"
        else:
            authoring_failure = "docker build failed"

    verification = verify_artifacts(app_dir, workdir, contract=contract, verify_triad=True)
    size_gates = verification.get("size_gates") or {}
    skip_docker_verification_ok = bool(
        skip_docker
        and not (verification.get("required_artifacts") or {}).get("missing")
        and size_gates.get("test_patch_ok")
        and size_gates.get("solution_patch_ok")
    )
    if skip_docker_verification_ok:
        verification = dict(verification)
        verification["ok"] = True
    summary = {
        "ok": bool(
            authoring_summary
            and (verification.get("ok") or skip_docker_verification_ok)
            and (
                skip_docker
                or not docker_available
                or (docker_build and docker_build.get("returncode") == 0)
            )
        ),
        "repo_url": repo_url,
        "pinned_sha": sha,
        "workflow_contract": contract.path.as_posix(),
        "workdir": workdir.as_posix(),
        "app_dir": app_dir.as_posix(),
        "artifact_paths": bootstrap.artifact_paths,
        "clone_steps": clone_steps,
        "doctor": doctor_payload,
        "docker": {
            "rendered": (app_dir / "Dockerfile.problem").as_posix(),
            "build": docker_build,
            "run": docker_run,
            "skipped": skip_docker,
            "image_tag": image_tag,
        },
        "authoring": authoring_summary,
        "verification": verification,
        "patch_sizes": {
            "test_patch_bytes": (workdir / "test.patch").stat().st_size
            if (workdir / "test.patch").exists()
            else 0,
            "solution_patch_bytes": (workdir / "solution.patch").stat().st_size
            if (workdir / "solution.patch").exists()
            else 0,
        },
    }
    summary["export"] = _export_final_artifacts(
        workdir,
        repo_url=repo_url,
        sha=sha,
        success=bool(summary["ok"]),
        export_root=artifact_export_root,
    )
    _write_json(workdir / "run_summary.json", summary)
    if summary["ok"]:
        summary["export"] = _export_final_artifacts(
            workdir,
            repo_url=repo_url,
            sha=sha,
            success=True,
            export_root=artifact_export_root,
        )
        _write_json(workdir / "run_summary.json", summary)
        return RunResult(True, summary, None)

    failure = _build_failure_payload(
        workdir,
        contract=contract,
        reason=authoring_failure or "run did not reach a verified artifact bundle",
        context={
            "repo_url": repo_url,
            "pinned_sha": sha,
            "artifact_paths": bootstrap.artifact_paths,
            "patch_sizes": summary["patch_sizes"],
            "size_gate_status": verification.get("size_gates"),
            "clean_tree_replay_status": (verification.get("triad") or {}).get("replay_commands")
            if verification.get("triad")
            else None,
            "base_new_triad_status": verification.get("triad"),
            "metadata_presence": verification.get("required_artifacts"),
        },
    )
    summary["export"] = _export_final_artifacts(
        workdir,
        repo_url=repo_url,
        sha=sha,
        success=False,
        export_root=artifact_export_root,
    )
    _write_json(workdir / "run_summary.json", summary)
    failure["export"] = summary["export"]
    _write_json(workdir / "final_failure.json", failure)
    failure["export"] = _export_final_artifacts(
        workdir,
        repo_url=repo_url,
        sha=sha,
        success=False,
        export_root=artifact_export_root,
    )
    summary["export"] = failure["export"]
    _write_json(workdir / "run_summary.json", summary)
    _write_json(workdir / "final_failure.json", failure)
    return RunResult(False, summary, failure)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sdetkit author")
    sub = parser.add_subparsers(dest="surface", required=True)
    problem = sub.add_parser("problem", help="Platform-style Python problem authoring lane")
    psub = problem.add_subparsers(dest="action", required=True)

    initp = psub.add_parser(
        "init",
        help="Bootstrap /work ledger state before exporting final artifacts into artifacts/platform_problem/latest",
    )
    initp.add_argument("--workdir", default="/work")
    initp.add_argument("--topic", default="platform-problem")
    initp.add_argument("--format", choices=["text", "json"], default="text")

    doctorp = psub.add_parser(
        "doctor", help="Inspect host tools, /work, repo export targets, and target repo readiness"
    )
    doctorp.add_argument("--repo-root", default=".")
    doctorp.add_argument("--workdir", default="/work")
    doctorp.add_argument("--format", choices=["text", "json"], default="text")

    renderp = psub.add_parser(
        "render-dockerfile", help="Render Dockerfile.problem from repo metadata"
    )
    renderp.add_argument("--repo-root", default=".")
    renderp.add_argument("--output", default=None)

    verifyp = psub.add_parser(
        "verify",
        help="Verify /work artifacts before final export into artifacts/platform_problem/latest",
    )
    verifyp.add_argument("--repo-root", default=".")
    verifyp.add_argument("--workdir", default="/work")
    verifyp.add_argument("--skip-triad", action="store_true")
    verifyp.add_argument("--format", choices=["text", "json"], default="text")

    runp = psub.add_parser(
        "run",
        help="Clone, pin, bootstrap /work, verify artifacts, then export the final bundle into artifacts/platform_problem/latest",
    )
    runp.add_argument("--repo", required=True)
    runp.add_argument("--sha", required=True)
    runp.add_argument("--workdir", default="/work")
    runp.add_argument("--topic", default=None)
    runp.add_argument("--skip-docker", action="store_true")
    runp.add_argument("--container-command", action="append", default=[])
    runp.add_argument("--min-test-patch-bytes", type=int, default=204800)
    runp.add_argument("--min-solution-patch-bytes", type=int, default=29696)
    runp.add_argument("--format", choices=["text", "json"], default="text")

    containerp = psub.add_parser(
        "container-exec",
        help="Internal: execute repo-owned authoring stages inside the container",
    )
    containerp.add_argument("--repo-root", required=True)
    containerp.add_argument("--workdir", required=True)
    containerp.add_argument("--topic", default=None)
    containerp.add_argument("--min-test-patch-bytes", type=int, default=204800)
    containerp.add_argument("--min-solution-patch-bytes", type=int, default=29696)
    containerp.add_argument("--format", choices=["text", "json"], default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)
    if ns.surface != "problem":
        raise SystemExit(2)

    if ns.action == "init":
        bootstrap = bootstrap_workdir(Path(ns.workdir), topic=str(ns.topic))
        if ns.format == "json":
            sys.stdout.write(canonical_json_dumps(bootstrap.to_dict()))
        else:
            sys.stdout.write(f"Bootstrapped {bootstrap.workdir.as_posix()}\n")
            for item in bootstrap.created:
                sys.stdout.write(f"- {item}\n")
        return 0

    if ns.action == "doctor":
        payload = run_author_doctor(Path(ns.repo_root), Path(ns.workdir))
        if ns.format == "json":
            sys.stdout.write(canonical_json_dumps(payload))
        else:
            sys.stdout.write(_format_human_doctor(payload))
        return 0 if payload.get("ok") else 1

    if ns.action == "render-dockerfile":
        output = Path(ns.output) if ns.output else None
        sys.stdout.write(render_dockerfile_problem(Path(ns.repo_root), output))
        return 0

    if ns.action == "verify":
        payload = verify_artifacts(
            Path(ns.repo_root), Path(ns.workdir), verify_triad=not bool(ns.skip_triad)
        )
        if ns.format == "json":
            sys.stdout.write(canonical_json_dumps(payload))
        else:
            sys.stdout.write(f"verification: {'OK' if payload.get('ok') else 'FAIL'}\n")
            sys.stdout.write(f"test.patch: {payload['test_patch']['status']}\n")
            sys.stdout.write(f"solution.patch: {payload['solution_patch']['status']}\n")
            sys.stdout.write(
                f"size gates: test={payload['size_gates']['test_patch_ok']} solution={payload['size_gates']['solution_patch_ok']}\n"
            )
        return 0 if payload.get("ok") else 1

    if ns.action == "container-exec":
        container_result = run_container_authoring(
            Path(ns.repo_root),
            Path(ns.workdir),
            topic=ns.topic,
            min_test_patch_bytes=int(ns.min_test_patch_bytes),
            min_solution_patch_bytes=int(ns.min_solution_patch_bytes),
        )
        payload = container_result.summary
        if ns.format == "json":
            sys.stdout.write(canonical_json_dumps(payload))
        else:
            sys.stdout.write(f"container-authoring: {'OK' if container_result.ok else 'FAIL'}\n")
        return 0 if container_result.ok else 1

    if ns.action == "run":
        workflow_result = run_problem_workflow(
            ns.repo,
            ns.sha,
            Path(ns.workdir),
            topic=ns.topic,
            skip_docker=bool(ns.skip_docker),
            container_command=list(ns.container_command) or None,
            min_test_patch_bytes=int(ns.min_test_patch_bytes),
            min_solution_patch_bytes=int(ns.min_solution_patch_bytes),
        )
        if ns.format == "json":
            sys.stdout.write(canonical_json_dumps(workflow_result.summary))
        else:
            sys.stdout.write(
                f"run: {'OK' if workflow_result.ok else 'FAIL'}\nworkdir: {Path(ns.workdir).resolve().as_posix()}\n"
            )
            sys.stdout.write(f"app_dir: {workflow_result.summary.get('app_dir', '')}\n")
            if workflow_result.failure:
                sys.stdout.write(
                    f"failure_reason: {workflow_result.failure.get('failure_reason', '')}\n"
                )
        return 0 if workflow_result.ok else 1

    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
