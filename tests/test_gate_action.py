"""The repository's GitHub Action (`uses: sherif69-sa/DevS69-sdetkit@v2`) runs the gate.

The steps' own shell scripts run here against small repositories, with the outputs,
job summary and `gh` that GitHub would provide replaced by files and a fake. Installing
sdetkit is the one step not run: the tests use the interpreter they run in, and the CI
job that runs the action on this repository covers the install.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from sdetkit.gates import gate

ROOT = Path(__file__).resolve().parents[1]
ACTION = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
STEPS = {step["name"]: step for step in ACTION["runs"]["steps"]}
EXPRESSION = re.compile(r"\$\{\{\s*(.+?)\s*\}\}")

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")


def _outputs(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    return dict(line.split("=", 1) for line in lines if "=" in line)


class Runner:
    """Runs one action step's script the way the composite action runs it."""

    def __init__(self, tmp_path: Path) -> None:
        self.temp = tmp_path / "runner-temp"
        self.temp.mkdir()
        self.summary = tmp_path / "step-summary.md"
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.values = {
            "inputs.args": "",
            "inputs.python": "",
            "inputs.fail-on": ACTION["inputs"]["fail-on"]["default"],
            "inputs.working-directory": ".",
            "inputs.github-token": "token",
            "steps.install.outputs.project-python": sys.executable,
            "steps.install.outputs.sdetkit-python": sys.executable,
            "github.event.pull_request.number": "7",
            "github.server_url": "https://github.com",
            "github.repository": "owner/repo",
            "github.run_id": "99",
        }

    def run(self, name: str, cwd: Path, **values: str) -> subprocess.CompletedProcess[str]:
        step = STEPS[name]
        self.output = cwd.parent / f"{step.get('id', 'step')}-output.txt"
        self.output.unlink(missing_ok=True)
        merged = {**self.values, **values}
        env = {
            **os.environ,
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "RUNNER_TEMP": str(self.temp),
            "GITHUB_OUTPUT": str(self.output),
            "GITHUB_STEP_SUMMARY": str(self.summary),
            "GITHUB_REPOSITORY": "owner/repo",
        }
        for key, value in (step.get("env") or {}).items():
            env[key] = EXPRESSION.sub(lambda match: merged[match.group(1)], str(value))
        return subprocess.run(
            ["bash", "-c", step["run"]], cwd=cwd, env=env, capture_output=True, text=True
        )

    def gate(self, repo: Path, **values: str) -> dict[str, str]:
        proc = self.run("Run sdetkit gate fast", repo, **values)
        assert proc.returncode == 0, proc.stderr
        outputs = _outputs(self.output)
        self.values["steps.gate.outputs.verdict"] = outputs["verdict"]
        self.values["steps.gate.outputs.summary"] = outputs["summary"]
        return outputs


def _repo(root: Path, test_body: str) -> Path:
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "1.0"\n')
    (root / "tests").mkdir()
    (root / "tests" / "test_demo.py").write_text(f"def test_demo():\n    {test_body}\n")
    return root


@pytest.fixture
def runner(tmp_path: Path) -> Runner:
    return Runner(tmp_path)


def test_a_failing_test_reads_no_ship_and_fails_the_step(tmp_path: Path, runner: Runner) -> None:
    repo = _repo(tmp_path / "repo", "assert 1 == 2")

    outputs = runner.gate(repo, **{"inputs.args": "--only pytest"})

    assert outputs["verdict"] == "NO_SHIP"
    assert outputs["exit-code"] == "2"
    report = json.loads(Path(outputs["report"]).read_text(encoding="utf-8"))
    assert report["verdict"]["decision"] == "NO_SHIP"
    summary = runner.summary.read_text(encoding="utf-8")
    # The repository has no environment of its own: the job's python ran its tests.
    assert f"Checks ran with `{sys.executable}` (--python)." in summary
    assert summary.startswith("### :x: SDETKit gate fast: NO_SHIP")
    assert "| `pytest` | :x: failed (exit 1) |" in summary

    applied = runner.run("Apply fail-on", repo)
    assert applied.returncode == 1
    assert "::error title=SDETKit gate::Verdict NO_SHIP" in applied.stdout
    assert runner.run("Apply fail-on", repo, **{"inputs.fail-on": "none"}).returncode == 0
    relaxed = runner.run("Apply fail-on", repo, **{"inputs.fail-on": "NOT_RUN, REVIEW"})
    assert relaxed.returncode == 0


def test_a_passing_repository_reads_ship(tmp_path: Path, runner: Runner) -> None:
    repo = _repo(tmp_path / "repo", "assert True")

    outputs = runner.gate(repo, **{"inputs.args": "--only pytest"})

    assert outputs["verdict"] == "SHIP"
    assert "SDETKit gate fast: SHIP" in runner.summary.read_text(encoding="utf-8")
    assert runner.run("Apply fail-on", repo).returncode == 0


def test_a_gate_that_writes_no_report_reads_not_run(tmp_path: Path, runner: Runner) -> None:
    repo = _repo(tmp_path / "repo", "assert True")

    outputs = runner.gate(repo, **{"inputs.args": "--no-such-option"})

    assert outputs["verdict"] == "NOT_RUN"
    assert "before writing a report" in runner.summary.read_text(encoding="utf-8")
    assert runner.run("Apply fail-on", repo).returncode == 1


def _fake_gh(runner: Runner) -> Path:
    log = runner.temp / "gh.log"
    script = runner.bin / "gh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$*" >> "{log}"\n'
        'case "$*" in *--jq*) printf "%s" "$FAKE_EXISTING"; exit 0;; esac\n'
        'while [ $# -gt 0 ]; do [ "$1" = --input ] && cat "$2" >> '
        f'"{log}"; shift; done\n'
    )
    script.chmod(0o755)
    return log


@pytest.mark.parametrize(
    ("existing", "call"),
    [("", "api --method POST repos/owner/repo/issues/7/comments"), ("42", "PATCH")],
)
def test_one_pull_request_comment_is_posted_then_updated(
    tmp_path: Path, runner: Runner, existing: str, call: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_EXISTING", existing)
    repo = _repo(tmp_path / "repo", "assert True")
    runner.gate(repo, **{"inputs.args": "--only pytest"})
    log = _fake_gh(runner)

    proc = runner.run("Comment on the pull request", repo)

    assert proc.returncode == 0, proc.stderr
    text = log.read_text(encoding="utf-8")
    assert call in text
    if existing:
        assert "repos/owner/repo/issues/comments/42" in text
    body = json.loads(text.splitlines()[-1])["body"]
    assert body.startswith("<!-- sdetkit-gate:. -->\n### :white_check_mark: SDETKit gate fast")
    assert body.rstrip().endswith("[Workflow run](https://github.com/owner/repo/actions/runs/99)")


def test_a_comment_that_cannot_be_posted_only_warns(tmp_path: Path, runner: Runner) -> None:
    repo = _repo(tmp_path / "repo", "assert True")
    runner.gate(repo, **{"inputs.args": "--only pytest"})
    (runner.bin / "gh").write_text("#!/usr/bin/env bash\nexit 1\n")
    (runner.bin / "gh").chmod(0o755)

    proc = runner.run("Comment on the pull request", repo)

    assert proc.returncode == 0
    assert "::warning title=SDETKit gate::Could not comment" in proc.stdout


def test_scripts_read_inputs_only_through_the_environment() -> None:
    """`${{ }}` inside a script would let a branch name or argument inject shell code."""

    declared = set(ACTION["inputs"])
    for step in ACTION["runs"]["steps"]:
        assert "${{" not in step["run"], step["name"]
        for value in (step.get("env") or {}).values():
            for expression in EXPRESSION.findall(str(value)):
                if expression.startswith("inputs."):
                    assert expression.removeprefix("inputs.") in declared
    assert set(ACTION["outputs"]) == {"verdict", "report", "summary"}
    install = STEPS["Install sdetkit"]["run"]
    assert '"$GITHUB_ACTION_PATH"' in install  # the tagged action installs its own source


def test_summary_out_appends_the_markdown_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path / "repo", "assert True")
    summary = tmp_path / "summary.md"
    summary.write_text("earlier step\n", encoding="utf-8")
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    args = ["fast", "--root", str(repo), "--only", "pytest", "--python", sys.executable]

    rc = gate.main([*args, "--format", "json", "--summary-out", str(summary)])

    assert rc == 0
    assert json.loads(capsys.readouterr().out)["verdict"]["decision"] == "SHIP"
    text = summary.read_text(encoding="utf-8")
    assert text.startswith("earlier step\n### :white_check_mark: SDETKit gate fast: SHIP\n")
    assert "| `pytest` | :white_check_mark: passed |" in text


def test_the_summary_leads_with_the_verdict_and_the_next_command() -> None:
    payload = {
        "ok": False,
        "steps": [
            {"id": "ruff", "ok": True, "rc": 0, "duration_ms": 1200},
            {
                "id": "pytest",
                "ok": False,
                "rc": 1,
                "environment_problem": "pytest could not import 'demo'",
            },
        ],
        "skipped_steps": [{"id": "mypy", "reason": "mypy is not configured | here"}],
        "next_action": {
            "first_failure": "No module named 'demo'",
            "classification": "environment",
            "next_command": "uv sync && python -m sdetkit gate fast",
        },
        "recommendations": ["uv sync && python -m sdetkit gate fast"],
        "verdict": {"decision": "NOT_RUN", "reasons": ["pytest: environment"]},
        "environment": {"python": "/repo/.venv/bin/python", "source": ".venv"},
    }

    text = gate._format_md(payload)

    assert text.splitlines()[0] == "### :white_circle: SDETKit gate fast: NOT_RUN"
    assert "| `ruff` | :white_check_mark: passed | 1.2s |" in text
    assert "| `pytest` | :white_circle: not run (environment) |" in text
    assert "| `mypy` | skipped: mypy is not configured \\| here | |" in text
    assert "**First failure (environment):** `No module named 'demo'`" in text
    assert "**Next:** `uv sync && python -m sdetkit gate fast`" in text
    assert text.count("uv sync") == 1  # the recommendation repeats the next command
    assert "- pytest: environment" in text
    assert text.rstrip().endswith("Nothing was applied, merged or dismissed.")
