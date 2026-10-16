"""The GitLab CI and Jenkins templates other repositories copy run the gate for real.

`examples/adoption/gitlab/sdetkit-gate.gitlab-ci.yml` and `examples/adoption/jenkins/sdetkit-gate.Jenkinsfile`
install the project the way its CI does, install SDETKit in an environment of its own and
run `gate fast`. The end-to-end tests execute each template's shell steps, in order, on a
fixture project, with SDETKit installed from this checkout instead of PyPI (the
`SDETKIT_PACKAGE` variable); they need the network and run in CI's "CI templates (self)" job.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
GITLAB = ROOT / "examples/adoption/gitlab/sdetkit-gate.gitlab-ci.yml"
JENKINS = ROOT / "examples/adoption/jenkins/sdetkit-gate.Jenkinsfile"
VERSION = re.search(
    r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M
)
# Keywords a GitLab CI job accepts (https://docs.gitlab.com/ci/yaml/), the ones used here.
GITLAB_JOB_KEYS = {
    "stage",
    "image",
    "variables",
    "rules",
    "before_script",
    "script",
    "after_script",
    "artifacts",
}


def _gitlab_job() -> dict[str, Any]:
    data = yaml.safe_load(GITLAB.read_text(encoding="utf-8"))
    assert list(data) == ["sdetkit-gate"]
    job: dict[str, Any] = data["sdetkit-gate"]
    return job


def _jenkins() -> tuple[dict[str, str], list[str], list[str]]:
    """The environment block, the stages' `sh` scripts in order, and the post scripts."""

    text = JENKINS.read_text(encoding="utf-8")
    environment = dict(re.findall(r"^\s*([A-Z_]+) = '([^']*)'$", text, re.M))
    stages, post = text.split("\n  post {", 1)
    scripts = [m[0] or m[1] for m in re.findall(r"sh '''(.*?)'''|sh '([^']*)'", stages, re.S)]
    post_scripts = re.findall(r"sh '([^']*)'", post)
    return environment, scripts, post_scripts


def test_the_gitlab_job_uses_known_keywords_and_keeps_the_report() -> None:
    job = _gitlab_job()

    assert set(job) <= GITLAB_JOB_KEYS
    assert all(isinstance(line, str) for key in ("before_script", "script") for line in job[key])
    assert job["artifacts"]["when"] == "always"
    assert job["artifacts"]["paths"] == ["build/sdetkit/"]
    # GitLab allows letters, digits, spaces, '-' and '_' in expose_as.
    assert re.fullmatch(r"[A-Za-z0-9 _-]+", job["artifacts"]["expose_as"])
    assert [rule["if"] for rule in job["rules"]] == [
        '$CI_PIPELINE_SOURCE == "merge_request_event"',
        "$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH",
    ]


def test_both_templates_pin_this_release() -> None:
    assert VERSION is not None
    pin = f"sdetkit=={VERSION[1]}"

    assert _gitlab_job()["variables"]["SDETKIT_PACKAGE"] == pin
    assert _jenkins()[0]["SDETKIT_PACKAGE"] == pin
    for path in (GITLAB, JENKINS):
        assert "gate fast" in path.read_text(encoding="utf-8")


def test_the_jenkinsfile_archives_what_the_gate_writes() -> None:
    _, scripts, post = _jenkins()
    text = JENKINS.read_text(encoding="utf-8")

    assert len(scripts) == 2
    assert "--out build/sdetkit/gate.json --summary-out build/sdetkit/gate.md" in scripts[1]
    assert "archiveArtifacts artifacts: 'build/sdetkit/**', allowEmptyArchive: true" in text
    assert post == ["cat build/sdetkit/gate.md 2>/dev/null || true"]


@pytest.mark.skipif(sys.platform == "win32", reason="the templates' steps are POSIX shell")
def test_every_shell_step_parses() -> None:
    job = _gitlab_job()
    _, scripts, post = _jenkins()
    steps = [
        "\n".join(job["before_script"] + job["script"]),
        "\n".join(job["after_script"]),
        *scripts,
        *post,
    ]

    for step in steps:
        proc = subprocess.run(["sh", "-n", "-c", step], capture_output=True, text=True)
        assert proc.returncode == 0, f"{step}\n{proc.stderr}"


def _project(root: Path, *, passing: bool) -> Path:
    (root / "src/app").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "app"\nversion = "0.1.0"\n\n'
        '[project.optional-dependencies]\ntest = ["pytest"]\n\n'
        '[tool.setuptools.packages.find]\nwhere = ["src"]\n'
    )
    (root / "src/app/__init__.py").write_text("def add(a, b):\n    return a + b\n")
    expected = 3 if passing else 4
    (root / "tests/test_add.py").write_text(
        f"from app import add\n\n\ndef test_add():\n    assert add(1, 2) == {expected}\n"
    )
    return root


def _agent(tmp_path: Path) -> dict[str, str]:
    """A CI machine: a fresh python on PATH (the image's or the agent's), nothing else."""

    image = tmp_path / "image"
    subprocess.run([sys.executable, "-m", "venv", str(image)], check=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("VIRTUAL_ENV", "PYTHON"))}
    env["PATH"] = f"{image / 'bin'}{os.pathsep}{os.environ['PATH']}"
    env["SDETKIT_PACKAGE"] = str(ROOT)
    return env


def _run(script: str, project: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", "-e", "-c", script],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )


def _verdict(project: Path) -> str:
    report = json.loads((project / "build/sdetkit/gate.json").read_text(encoding="utf-8"))
    decision: str = report["verdict"]["decision"]
    assert decision in (project / "build/sdetkit/gate.md").read_text(encoding="utf-8")
    return decision


@pytest.mark.network
@pytest.mark.skipif(sys.platform == "win32", reason="the templates' steps are POSIX shell")
@pytest.mark.parametrize(("passing", "verdict"), [(True, "SHIP"), (False, "NO_SHIP")])
def test_the_gitlab_job_runs_the_gate(tmp_path: Path, passing: bool, verdict: str) -> None:
    job = _gitlab_job()
    project = _project(tmp_path / "app", passing=passing)
    env = {**_agent(tmp_path), "CI_PROJECT_DIR": str(project), "SDETKIT_ARGS": ""}

    proc = _run("\n".join(job["before_script"] + job["script"]), project, env)
    after = _run("\n".join(job["after_script"]), project, env)

    assert (proc.returncode == 0) is passing, proc.stdout + proc.stderr
    # SHIP and NO_SHIP both mean pytest imported the project, which before_script installed
    # only in the job's python: SDETKit's own environment would read NOT_RUN.
    assert _verdict(project) == verdict
    report = json.loads((project / "build/sdetkit/gate.json").read_text(encoding="utf-8"))
    assert [step["id"] for step in report["steps"]] == ["doctor", "pytest"]
    assert f"SDETKit gate fast: {verdict}" in after.stdout


@pytest.mark.network
@pytest.mark.skipif(sys.platform == "win32", reason="the templates' steps are POSIX shell")
@pytest.mark.parametrize(("passing", "verdict"), [(True, "SHIP"), (False, "NO_SHIP")])
def test_the_jenkins_pipeline_runs_the_gate(tmp_path: Path, passing: bool, verdict: str) -> None:
    environment, scripts, post = _jenkins()
    project = _project(tmp_path / "app", passing=passing)
    env = {**environment, **_agent(tmp_path)}

    setup = _run(scripts[0], project, env)
    gate = _run(scripts[1], project, env)
    after = _run(post[0], project, env)

    assert setup.returncode == 0, setup.stdout + setup.stderr
    assert (gate.returncode == 0) is passing, gate.stdout + gate.stderr
    assert _verdict(project) == verdict
    # The setup stage's .venv is where the checks ran.
    assert (project / ".venv").is_dir()
    assert f"SDETKit gate fast: {verdict}" in after.stdout
