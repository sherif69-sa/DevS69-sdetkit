from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import _toml
from .atomicio import atomic_write_text, canonical_json_dumps

_BASE_IMAGE = "public.ecr.aws/x8v8d7g8/mars-base:latest"
_DEFAULT_WORKFLOW_PATH = Path(".sdetkit/workflows/platform_problem.yaml")
_ALLOWED_TEST_METADATA_EDIT = "tests/conftest.py"
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
        return DockerInvocation(argv=argv, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)

    def which(self, program: str) -> str | None:
        return shutil.which(program)


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "phases": [phase.to_dict() for phase in self.phases],
            "clean_tree_ok": self.clean_tree_ok,
            "clean_tree_details": list(self.clean_tree_details),
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
class RunContext:
    repo_url: str
    sha: str
    workdir: Path
    app_dir: Path
    topic: str
    contract: WorkflowContract
    bootstrap: WorkBootstrap


@dataclass(frozen=True)
class RunResult:
    ok: bool
    summary: dict[str, Any]
    failure: dict[str, Any] | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_workflow_contract(path: Path | None = None) -> WorkflowContract:
    candidates: list[Path] = []
    if path is not None:
        candidates.append(Path(path))
    cwd_candidate = Path.cwd() / _DEFAULT_WORKFLOW_PATH
    repo_candidate = _repo_root() / _DEFAULT_WORKFLOW_PATH
    candidates.extend([cwd_candidate, repo_candidate])
    for candidate in candidates:
        if candidate.exists():
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            return WorkflowContract(path=candidate, payload=payload)
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
            "## public-surface scan\n- list existing tests, docs, and CLI/contracts reviewed.\n\n"
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
        artifact = workdir / name
        _write_if_missing(artifact, "", created)
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
        workdir=workdir, submission_dir=submission_dir, created=created, artifact_paths=artifact_paths
    )


def generate_test_runner(topic: str) -> str:
    slug = _slugify(topic)
    return (
        "#!/usr/bin/env bash\n\n"
        "set -euo pipefail\n\n"
        'mode=${1:-}\n'
        'case "$mode" in\n'
        f'  new) python3 -m pytest tests/test_{slug}_problem.py ;;\n'
        f'  base) python3 -m pytest tests --ignore=tests/test_{slug}_problem.py ;;\n'
        '  *) echo "Usage: $0 {base|new}" >&2; exit 2 ;;\n'
        "esac\n"
    )


def ensure_minimal_test_runner(repo_root: Path, *, topic: str) -> Path:
    path = Path(repo_root) / "test.sh"
    atomic_write_text(path, generate_test_runner(topic))
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
    if "pyproject.toml" in metadata_files:
        baseline_commands.append("python3 -m pytest")
    elif requirements_files:
        baseline_commands.append("python3 -m pytest")
        risks.append("pytest dependencies inferred from requirements*.txt rather than pyproject metadata")
    else:
        baseline_commands.append("python3 -m pytest")
        risks.append("no pyproject.toml or requirements*.txt found; Dockerfile.problem may need inferred deps")
    if "tox.ini" in metadata_files:
        baseline_commands.append("python3 -m tox -q")
    if "noxfile.py" in metadata_files:
        baseline_commands.append("python3 -m nox -s tests")
    long_horizon_notes: list[str] = []
    py_files = list(repo_root.glob("src/**/*.py")) + list(repo_root.glob("**/*.py"))
    top_level_public = 0
    for package_dir in [repo_root / "src", repo_root]:
        if package_dir.exists():
            top_level_public += len([p for p in package_dir.iterdir() if p.suffix == ".py"])
    if top_level_public >= 3:
        long_horizon_notes.append("multiple public Python entrypoints detected")
    tests_dir = repo_root / "tests"
    if tests_dir.exists() and len(list(tests_dir.glob("test_*.py"))) >= 10:
        long_horizon_notes.append("broad existing test surface suggests richer behavioral contracts")
    if len(py_files) >= 20:
        long_horizon_notes.append("cross-module production surface appears large enough for multi-file fixes")
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
    requirements_files = [p.name for p in sorted(repo_root.glob("requirements*.txt")) if p.is_file()]
    inferred_packages: set[str] = set()
    pyproject = repo_root / "pyproject.toml"
    pyproject_payload: dict[str, Any] = {}
    project_dependencies: list[str] = []
    extras: list[str] = []
    if pyproject.exists():
        pyproject_payload = _toml.loads(pyproject.read_text(encoding="utf-8"))
        project = pyproject_payload.get("project", {})
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
    for rel in ["tox.ini", "noxfile.py", ".github/workflows", ".gitlab-ci.yml", "azure-pipelines.yml"]:
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
    lines = [
        f"FROM {_BASE_IMAGE}",
        "WORKDIR /app",
        "COPY . /app",
    ]
    for req in install_inputs["requirements_files"]:
        lines.append(f"RUN python3 -m pip install --no-cache-dir -r {req}")
    if (repo_root / "pyproject.toml").exists():
        if install_inputs["extras"]:
            extra_text = ",".join(install_inputs["extras"])
            lines.append(f'RUN python3 -m pip install --no-cache-dir ".[{extra_text}]"')
        else:
            lines.append("RUN python3 -m pip install --no-cache-dir .")
    elif install_inputs["project_dependencies"]:
        joined = " ".join(sorted(install_inputs["project_dependencies"]))
        lines.append(f"RUN python3 -m pip install --no-cache-dir {joined}")
    if install_inputs["inferred_packages"]:
        lines.append(
            "RUN python3 -m pip install --no-cache-dir "
            + " ".join(sorted(install_inputs["inferred_packages"]))
        )
    lines.append('CMD ["/bin/bash"]')
    text = "\n".join(lines) + "\n"
    target = output_path or (repo_root / "Dockerfile.problem")
    atomic_write_text(target, text)
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
) -> DockerInvocation:
    runner = runner or DockerCommandRunner()
    command = command or ["/bin/bash"]
    argv = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{Path(repo_root).resolve()}:/app",
        "-v",
        f"{Path(workdir).resolve()}:/work",
        "-w",
        "/app",
        image,
        *command,
    ]
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


def analyze_test_patch(patch_path: Path) -> PatchAnalysis:
    exists = patch_path.exists()
    size_bytes = patch_path.stat().st_size if exists else 0
    files = _patch_paths(patch_path)
    errors: list[str] = []
    warnings: list[str] = []
    if not exists:
        errors.append("test.patch is missing")
        return PatchAnalysis(patch_path, exists, size_bytes, files, "fail", errors, warnings)
    allowed_test_files = [path for path in files if path.startswith("tests/test_") and path.endswith("_problem.py")]
    disallowed = []
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
    if disallowed:
        errors.append("test.patch contains disallowed paths: " + ", ".join(disallowed))
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
        or file in {"Dockerfile", "Dockerfile.problem", "docker.file", "final_title.txt", "final_description.txt"}
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
    shutil.copytree(src, dest, symlinks=False, ignore=shutil.ignore_patterns(".git"))


def _run_test_mode(mode: str, *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", "test.sh", mode], cwd=str(cwd), text=True, capture_output=True)


def _apply_patch(repo_root: Path, patch_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "apply", str(patch_path)], cwd=str(repo_root), text=True, capture_output=True
    )


def _apply_patch_check(repo_root: Path, patch_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "apply", "--check", str(patch_path)], cwd=str(repo_root), text=True, capture_output=True
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
            details.append(clone_proc.stderr.strip())
            if clone_proc.returncode == 0:
                checkout_proc = subprocess.run(
                    ["git", "checkout", "--quiet", sha],
                    cwd=str(destination),
                    text=True,
                    capture_output=True,
                )
                details.append(checkout_proc.stderr.strip())
                return checkout_proc.returncode == 0, [item for item in details if item]
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
    with tempfile.TemporaryDirectory(prefix="sdetkit-triad-") as tmp:
        starter = Path(tmp) / "starter"
        clean_tree_ok, details = _materialize_starter_tree(Path(repo_root).resolve(), starter)
        clean_tree_details.extend(details)
        if not clean_tree_ok:
            return TriadResult(ok=False, phases=phases, clean_tree_ok=False, clean_tree_details=clean_tree_details)
        checks = [
            _apply_patch_check(starter, test_patch),
            _apply_patch_check(starter, solution_patch),
        ]
        for proc in checks:
            if proc.returncode != 0:
                clean_tree_ok = False
                clean_tree_details.append(proc.stderr.strip() or proc.stdout.strip())
        test_patch_already_applied = False
        base_tree = starter
        if not (starter / "test.sh").exists():
            apply_test_for_runner = _apply_patch(starter, test_patch)
            if apply_test_for_runner.returncode != 0:
                clean_tree_ok = False
                clean_tree_details.append(
                    apply_test_for_runner.stderr.strip() or apply_test_for_runner.stdout.strip()
                )
                return TriadResult(
                    ok=False,
                    phases=phases,
                    clean_tree_ok=clean_tree_ok,
                    clean_tree_details=clean_tree_details,
                )
            test_patch_already_applied = True
        base_proc = _run_test_mode("base", cwd=base_tree)
        phases.append(
            TriadPhase(
                name="starter_base",
                command="bash test.sh base",
                expected="pass",
                returncode=base_proc.returncode,
                stdout=base_proc.stdout,
                stderr=base_proc.stderr,
                ok=base_proc.returncode == 0,
            )
        )
        if not test_patch_already_applied:
            apply_test = _apply_patch(starter, test_patch)
            if apply_test.returncode != 0:
                clean_tree_ok = False
                clean_tree_details.append(apply_test.stderr.strip() or apply_test.stdout.strip())
                return TriadResult(
                    ok=False,
                    phases=phases,
                    clean_tree_ok=clean_tree_ok,
                    clean_tree_details=clean_tree_details,
                )
        new_proc = _run_test_mode("new", cwd=starter)
        phases.append(
            TriadPhase(
                name="test_patch_new",
                command="bash test.sh new",
                expected="fail",
                returncode=new_proc.returncode,
                stdout=new_proc.stdout,
                stderr=new_proc.stderr,
                ok=new_proc.returncode != 0,
            )
        )
        apply_solution = _apply_patch(starter, solution_patch)
        if apply_solution.returncode != 0:
            clean_tree_ok = False
            clean_tree_details.append(apply_solution.stderr.strip() or apply_solution.stdout.strip())
            return TriadResult(ok=False, phases=phases, clean_tree_ok=clean_tree_ok, clean_tree_details=clean_tree_details)
        final_base = _run_test_mode("base", cwd=starter)
        phases.append(
            TriadPhase(
                name="solution_base",
                command="bash test.sh base",
                expected="pass",
                returncode=final_base.returncode,
                stdout=final_base.stdout,
                stderr=final_base.stderr,
                ok=final_base.returncode == 0,
            )
        )
        final_new = _run_test_mode("new", cwd=starter)
        phases.append(
            TriadPhase(
                name="solution_new",
                command="bash test.sh new",
                expected="pass",
                returncode=final_new.returncode,
                stdout=final_new.stdout,
                stderr=final_new.stderr,
                ok=final_new.returncode == 0,
            )
        )
    ok = clean_tree_ok and all(phase.ok for phase in phases)
    return TriadResult(ok=ok, phases=phases, clean_tree_ok=clean_tree_ok, clean_tree_details=clean_tree_details)


def _check_ascii_title(title: str) -> list[str]:
    errors: list[str] = []
    if not title.strip():
        errors.append("final_title.txt is empty")
    if not title.isascii():
        errors.append("final_title.txt must be ASCII-only")
    return errors


def _check_final_description(description: str) -> list[str]:
    errors: list[str] = []
    words = [word for word in re.split(r"\s+", description.strip()) if word]
    if not description.strip():
        errors.append("final_description.txt is empty")
        return errors
    if not description.isascii():
        errors.append("final_description.txt must be ASCII-only")
    if len(words) < 77 or len(words) > 88:
        errors.append("final_description.txt must contain 77-88 words")
    if "test" in description.lower() or "pytest" in description.lower():
        errors.append("final_description.txt must not reference tests")
    if "solution" in description.lower() or "fix" in description.lower():
        errors.append("final_description.txt must not include solution hints")
    if "- " not in description and "* " not in description:
        errors.append("final_description.txt must contain a code-like bullet block")
    return errors


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, canonical_json_dumps(payload))


def _write_failure(workdir: Path, *, reason: str, context: dict[str, Any]) -> dict[str, Any]:
    payload = {"ok": False, "reason": reason, **context}
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
    checks: list[dict[str, Any]] = []
    writable = os.access(workdir, os.W_OK)
    checks.append({"id": "git_available", "ok": runner.which("git") is not None})
    checks.append({"id": "docker_available", "ok": runner.which("docker") is not None})
    checks.append({"id": "workdir_writable", "ok": writable})
    checks.append({"id": "ledger_bootstrap", "ok": bool(bootstrap.created) or workdir.exists()})
    checks.append({"id": "metadata_present", "ok": bool(inspection.metadata_files or inspection.requirements_files)})
    checks.append({"id": "repo_long_horizon_fit", "ok": inspection.likely_long_horizon_fit})
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
    docker_sync_ok = docker_problem.exists() and docker_copy.exists() and docker_problem.read_text(encoding="utf-8") == docker_copy.read_text(encoding="utf-8")
    metadata_errors: list[str] = []
    final_title = (workdir / "final_title.txt").read_text(encoding="utf-8") if (workdir / "final_title.txt").exists() else ""
    final_description = (workdir / "final_description.txt").read_text(encoding="utf-8") if (workdir / "final_description.txt").exists() else ""
    metadata_errors.extend(_check_ascii_title(final_title))
    metadata_errors.extend(_check_final_description(final_description))
    triad = None
    if verify_triad:
        triad = verify_clean_tree_and_triad(
            repo_root,
            test_patch=workdir / "test.patch",
            solution_patch=workdir / "solution.patch",
        )
    ok = (
        test_patch.status == "pass"
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
        _write_failure(workdir, reason="artifact verification failed", context=payload)
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
) -> RunResult:
    runner = runner or DockerCommandRunner()
    contract = contract or load_workflow_contract()
    if min_test_patch_bytes is not None:
        contract.payload.setdefault("size_gates", {})["test_patch_min_bytes"] = min_test_patch_bytes
    if min_solution_patch_bytes is not None:
        contract.payload.setdefault("size_gates", {})["solution_patch_min_bytes"] = min_solution_patch_bytes
    bootstrap = bootstrap_workdir(workdir, topic=topic)
    app_dir = Path(workdir).resolve() / "app"
    if app_dir.exists() and any(app_dir.iterdir()):
        failure = _write_failure(Path(workdir), reason="/work/app already exists and is not empty", context={"app_dir": app_dir.as_posix()})
        return RunResult(ok=False, summary=failure, failure=failure)
    clone_steps = _git_clone_and_checkout(repo_url, sha, app_dir)
    if any(step["returncode"] != 0 for step in clone_steps):
        failure = _write_failure(Path(workdir), reason="git clone or checkout failed", context={"steps": clone_steps})
        return RunResult(ok=False, summary=failure, failure=failure)
    topic_slug = _slugify(topic or app_dir.name)
    inspection = inspect_repo_metadata(app_dir)
    render_dockerfile_problem(app_dir)
    _copy_docker_artifact(app_dir, Path(workdir))
    ensure_minimal_test_runner(app_dir, topic=topic_slug)
    doctor_payload = run_author_doctor(app_dir, Path(workdir), contract=contract, runner=runner)
    docker_build = None
    docker_run = None
    image_tag = f"sdetkit-author-{topic_slug}"
    if not skip_docker:
        docker_build = build_docker_image(app_dir, tag=image_tag, runner=runner).to_dict()
        if docker_build["returncode"] == 0:
            docker_run = run_authoring_container(
                app_dir,
                Path(workdir),
                image=image_tag,
                command=container_command,
                runner=runner,
            ).to_dict()
    summary = {
        "ok": False,
        "repo_url": repo_url,
        "pinned_sha": sha,
        "workflow_contract": contract.path.as_posix(),
        "workdir": Path(workdir).resolve().as_posix(),
        "app_dir": app_dir.as_posix(),
        "artifacts": bootstrap.artifact_paths,
        "bootstrap": bootstrap.to_dict(),
        "doctor": doctor_payload,
        "inspection": inspection.to_dict(),
        "docker": {
            "rendered": (app_dir / "Dockerfile.problem").as_posix(),
            "build": docker_build,
            "run": docker_run,
            "skipped": skip_docker,
        },
        "gating_order": contract.payload.get("gating_order", []),
        "notes": {
            "novelty_gate": (Path(workdir) / "novelty_gate.txt").as_posix(),
            "candidate_notes": (Path(workdir) / "candidate_notes.md").as_posix(),
        },
    }
    verification = verify_artifacts(app_dir, Path(workdir), contract=contract, verify_triad=False)
    summary["verification"] = verification
    summary["patch_sizes"] = {
        "test_patch_bytes": Path(workdir, "test.patch").stat().st_size,
        "solution_patch_bytes": Path(workdir, "solution.patch").stat().st_size,
    }
    summary["ok"] = bool(
        doctor_payload.get("ok")
        and (skip_docker or (docker_build and docker_build.get("returncode") == 0))
        and verification.get("ok")
    )
    _write_json(Path(workdir) / "run_summary.json", summary)
    if not summary["ok"]:
        failure = _write_failure(Path(workdir), reason="run did not reach a verified artifact bundle", context=summary)
        return RunResult(ok=False, summary=summary, failure=failure)
    return RunResult(ok=True, summary=summary, failure=None)


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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sdetkit author")
    sub = parser.add_subparsers(dest="surface", required=True)
    problem = sub.add_parser("problem", help="Platform-style Python problem authoring lane")
    psub = problem.add_subparsers(dest="action", required=True)

    initp = psub.add_parser("init", help="Bootstrap /work ledger state and artifact targets")
    initp.add_argument("--workdir", default="/work")
    initp.add_argument("--topic", default="platform-problem")
    initp.add_argument("--format", choices=["text", "json"], default="text")

    doctorp = psub.add_parser("doctor", help="Inspect host tools, /work, and target repo readiness")
    doctorp.add_argument("--repo-root", default=".")
    doctorp.add_argument("--workdir", default="/work")
    doctorp.add_argument("--format", choices=["text", "json"], default="text")

    renderp = psub.add_parser("render-dockerfile", help="Render Dockerfile.problem from repo metadata")
    renderp.add_argument("--repo-root", default=".")
    renderp.add_argument("--output", default=None)

    verifyp = psub.add_parser("verify", help="Verify artifact boundaries, size gates, and triad replay")
    verifyp.add_argument("--repo-root", default=".")
    verifyp.add_argument("--workdir", default="/work")
    verifyp.add_argument("--skip-triad", action="store_true")
    verifyp.add_argument("--format", choices=["text", "json"], default="text")

    runp = psub.add_parser("run", help="Clone, pin, bootstrap, render Dockerfile, and verify artifacts")
    runp.add_argument("--repo", required=True)
    runp.add_argument("--sha", required=True)
    runp.add_argument("--workdir", default="/work")
    runp.add_argument("--topic", default=None)
    runp.add_argument("--skip-docker", action="store_true")
    runp.add_argument("--container-command", action="append", default=[])
    runp.add_argument("--min-test-patch-bytes", type=int, default=204800)
    runp.add_argument("--min-solution-patch-bytes", type=int, default=29696)
    runp.add_argument("--format", choices=["text", "json"], default="text")
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
        text = render_dockerfile_problem(Path(ns.repo_root), output)
        sys.stdout.write(text)
        return 0

    if ns.action == "verify":
        payload = verify_artifacts(
            Path(ns.repo_root),
            Path(ns.workdir),
            verify_triad=not bool(ns.skip_triad),
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

    if ns.action == "run":
        container_command = list(ns.container_command) or None
        result = run_problem_workflow(
            ns.repo,
            ns.sha,
            Path(ns.workdir),
            topic=ns.topic,
            skip_docker=bool(ns.skip_docker),
            container_command=container_command,
            min_test_patch_bytes=int(ns.min_test_patch_bytes),
            min_solution_patch_bytes=int(ns.min_solution_patch_bytes),
        )
        if ns.format == "json":
            sys.stdout.write(canonical_json_dumps(result.summary))
        else:
            sys.stdout.write(
                f"run: {'OK' if result.ok else 'FAIL'}\nworkdir: {Path(ns.workdir).resolve().as_posix()}\n"
            )
            sys.stdout.write(f"app_dir: {result.summary.get('app_dir', '')}\n")
            if result.failure:
                sys.stdout.write(f"failure_reason: {result.failure.get('reason', '')}\n")
        return 0 if result.ok else 1

    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
