#!/usr/bin/env python3
"""Run `gate fast` on well-known open-source repositories and publish what happened.

    python scripts/external_repo_proof.py run --workdir /tmp/external-repos
    python scripts/external_repo_proof.py render [--check]

`run` clones each repository below at its pinned commit and runs `gate fast` twice: on
the fresh clone, then again after the setup command SDETKit itself suggests for that
repository (`sdetkit.gates.project_env.setup_command`). It needs network access to
GitHub and the package indexes, and writes `docs/artifacts/external-repo-proof/results.json`.

`render` turns that file into `docs/external-repo-proof.md`; `--check` fails when the page
is out of date. Results are recorded as they come out, including the ones that are wrong:
each repository's notes say which outcomes are true and which are SDETKit gaps.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/artifacts/external-repo-proof/results.json"
PAGE = ROOT / "docs/external-repo-proof.md"
SCHEMA_VERSION = "sdetkit.external_repo_proof.v1"

GAP = "gap"
TRUE = "true"
ENVIRONMENT = "environment"

# name, clone URL, pinned commit, and what each recorded outcome means.
REPOS: list[dict[str, Any]] = [
    {
        "name": "pallets/itsdangerous",
        "url": "https://github.com/pallets/itsdangerous",
        "commit": "672971d66a2ef9f85151e53283113f33d642dabd",
        "notes": [
            (TRUE, "Fresh clone: NOT_RUN is right. The src-layout package is not installed yet."),
            (TRUE, "After `uv sync`: SHIP from the project's own ruff, mypy and pytest."),
        ],
    },
    {
        "name": "pallets/markupsafe",
        "url": "https://github.com/pallets/markupsafe",
        "commit": "4e111271b1494995708a9e878a10829b5e10c7ba",
        "notes": [
            (
                TRUE,
                "Fresh clone: NOT_RUN is right. mypy failed only inside numpy stubs installed "
                "next to SDETKit, not in this repository.",
            ),
            (TRUE, "After `uv sync`: SHIP, with the tests importing the checkout."),
        ],
    },
    {
        "name": "pallets/click",
        "url": "https://github.com/pallets/click",
        "commit": "2247b35ea1c47c727d7a06e51fa280e12a863ff6",
        "notes": [
            (
                GAP,
                "Fresh clone: NO_SHIP is wrong. The tests imported the click release installed "
                "next to SDETKit, not this checkout, and SDETKit does not notice.",
            ),
            (TRUE, "After `uv sync`: SHIP."),
        ],
    },
    {
        "name": "python-attrs/attrs",
        "url": "https://github.com/python-attrs/attrs",
        "commit": "ee66e7274852438cc23d4240a1a9cd632fda8b52",
        "notes": [
            (
                GAP,
                "mypy NO_SHIP is wrong. attrs configures mypy without `files` and type-checks "
                "only its `.pyi` stubs (tox `mypy` env); SDETKit falls back to `mypy src`, which "
                "the project never runs.",
            ),
            (
                GAP,
                "Fresh clone: NO_SHIP is wrong. The tests imported the attrs release installed "
                "next to SDETKit, without the project's test dependencies.",
            ),
            (
                TRUE,
                "After `uv sync`: the pytest failures are the project's own in this environment "
                "(a pyright baseline test that depends on the pyright version).",
            ),
        ],
    },
    {
        "name": "pytest-dev/pluggy",
        "url": "https://github.com/pytest-dev/pluggy",
        "commit": "21c7e1672941a0cd9e3c555bf5e5007f1fbe3dc5",
        "notes": [
            (TRUE, "Fresh clone: NOT_RUN is right. pluggy is not installed yet."),
            (TRUE, "After `uv sync`: SHIP."),
        ],
    },
    {
        "name": "python-poetry/poetry-core",
        "url": "https://github.com/python-poetry/poetry-core",
        "commit": "b52c25c451bbaed9f309d45fc6e6e35c704e55bf",
        "notes": [
            (
                GAP,
                "Fresh clone: NO_SHIP is wrong. mypy could not find `tomli_w`, a dependency "
                "that is not installed next to SDETKit.",
            ),
            (
                TRUE,
                "After `poetry install`: SHIP, found through `poetry env info` (Poetry keeps "
                "the environment outside the repository).",
            ),
        ],
    },
    {
        "name": "psf/requests",
        "url": "https://github.com/psf/requests",
        "commit": "611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60",
        "notes": [
            (
                GAP,
                "Fresh clone: the pytest failure is wrong. The tests imported the requests "
                "release installed next to SDETKit, and 205 errored for want of the project's "
                "test dependencies.",
            ),
            (
                GAP,
                "ruff_format NO_SHIP is wrong. requests excludes `tests/test_lowlevel.py` from "
                "its pre-commit `ruff-format` hook; SDETKit checks the file anyway.",
            ),
            (
                GAP,
                "The suggested setup installs the package but not `requirements-dev.txt`, so "
                "the project environment has no pytest and the tests do not run.",
            ),
        ],
    },
]


def _run(cmd: list[str], cwd: Path, *, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    return subprocess.run(
        cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, check=False
    )


def _tool_version(tool: str) -> str:
    if shutil.which(tool) is None:
        return "not installed"
    proc = subprocess.run([tool, "--version"], capture_output=True, text=True, check=False)
    return proc.stdout.strip() or proc.stderr.strip()


def _clone(url: str, commit: str, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    # Blobless, with history and tags: projects that derive their version from git need them.
    subprocess.run(
        ["git", "clone", "-q", "--filter=blob:none", "--no-checkout", url, str(dest)], check=True
    )
    subprocess.run(["git", "-C", str(dest), "checkout", "-q", commit], check=True)


def _first_line(text: str, limit: int = 240) -> str:
    line = " ".join(text.split())
    return line if len(line) <= limit else line[: limit - 3] + "..."


def _gate(repo: Path, out: Path) -> dict[str, Any]:
    started = time.time()
    proc = _run(
        [sys.executable, "-m", "sdetkit", "gate", "fast", "--format", "json", "--out", str(out)],
        repo,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    card = payload.get("next_action", {})
    return {
        "rc": proc.returncode,
        "seconds": round(time.time() - started),
        "decision": payload["verdict"]["decision"],
        "environment": payload.get("environment", {}).get("source", ""),
        "steps": [
            {"id": step["id"], "ok": bool(step.get("ok"))} for step in payload.get("steps", [])
        ],
        "skipped_steps": [step["id"] for step in payload.get("skipped_steps", [])],
        "failed_steps": payload.get("failed_steps", []),
        "classification": card.get("classification", ""),
        "first_failure": _first_line(str(card.get("first_failure", ""))),
        "affected_file": card.get("affected_file", ""),
        "next_command": card.get("next_command", ""),
    }


def run(workdir: Path, runner_note: str) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "src"))
    from sdetkit.gates.project_env import setup_command
    from sdetkit.lockfiles import python_lockfiles

    # The SDETKit code under test is the checkout as the run starts.
    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    workdir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for spec in REPOS:
        repo = workdir / spec["name"].split("/")[1]
        print(f"== {spec['name']}", file=sys.stderr)
        _clone(spec["url"], spec["commit"], repo)
        fresh = _gate(repo, workdir / f"{repo.name}.fresh.json")
        setup = setup_command(repo)
        proc = _run(["bash", "-c", setup], repo)
        after = _gate(repo, workdir / f"{repo.name}.after-setup.json")
        results.append(
            {
                "name": spec["name"],
                "url": spec["url"],
                "commit": spec["commit"],
                "lockfiles": python_lockfiles(repo),
                "setup_command": setup,
                "setup_rc": proc.returncode,
                "fresh_clone": fresh,
                "after_setup": after,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "recorded_on": time.strftime("%Y-%m-%d", time.gmtime()),
        "sdetkit_commit": head.stdout.strip(),
        "runner": {
            "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.machine()}",
            "uv": _tool_version("uv"),
            "poetry": _tool_version("poetry"),
            "note": runner_note,
        },
        "repositories": results,
    }


def _stage(result: dict[str, Any]) -> str:
    return f"**{result['decision']}**"


def _steps(result: dict[str, Any]) -> str:
    marks = [f"{step['id']} {'✅' if step['ok'] else '❌'}" for step in result["steps"]]
    return ", ".join(marks) or "none"


def _stage_lines(label: str, result: dict[str, Any]) -> list[str]:
    lines = [
        f"- **{label}:** {result['decision']} (exit {result['rc']}, {result['seconds']}s, "
        f"python from `{result['environment']}`). Steps: {_steps(result)}.",
    ]
    if result["failed_steps"]:
        lines.append(
            f"  - First failure ({result['classification'] or 'unclassified'}): "
            f"`{result['first_failure']}`"
        )
        lines.append(f"  - Next command: `{result['next_command']}`")
    return lines


def _notes(name: str) -> list[tuple[str, str]]:
    return next((list(spec["notes"]) for spec in REPOS if spec["name"] == name), [])


def render(data: dict[str, Any]) -> str:
    repos = data["repositories"]
    runner = data["runner"]
    gaps = [(r["name"], text) for r in repos for kind, text in _notes(r["name"]) if kind == GAP]
    out = [
        "# External repository proof",
        "",
        "SDETKit's `gate fast`, run on well-known open-source Python projects at pinned "
        "commits. Each project is run twice: on a fresh clone, and again after the setup "
        "command SDETKit suggests for it. Every outcome is recorded as it came out, including "
        "the ones SDETKit gets wrong; the notes under each project say which is which.",
        "",
        f"Recorded on {data['recorded_on']} with SDETKit at commit "
        f"`{data['sdetkit_commit'][:12]}`, Python {runner['python']} on {runner['platform']}, "
        f"{runner['uv']}, {runner['poetry']}.",
    ]
    if runner.get("note"):
        out += ["", runner["note"]]
    out += [
        "",
        "## Results",
        "",
        "| Project | Commit | Fresh clone | Setup command | After setup |",
        "| --- | --- | --- | --- | --- |",
    ]
    for repo in repos:
        out.append(
            f"| [{repo['name']}]({repo['url']}) | `{repo['commit'][:12]}` | "
            f"{_stage(repo['fresh_clone'])} | `{repo['setup_command']}` | "
            f"{_stage(repo['after_setup'])} |"
        )
    out += [
        "",
        "`NOT_RUN` means the checks could not run against the repository, and the next command "
        "says how to fix that. `NO_SHIP` means a check failed.",
        "",
        "## Gaps this proof found in SDETKit",
        "",
    ]
    out += [f"- {name}: {text}" for name, text in gaps] or ["None."]
    out += ["", "## Per project", ""]
    for repo in repos:
        out += [f"### {repo['name']}", ""]
        out.append(
            f"Commit [`{repo['commit'][:12]}`]({repo['url']}/tree/{repo['commit']}), "
            f"lockfiles: {', '.join(f'`{f}`' for f in repo['lockfiles']) or 'none'}, "
            f"setup: `{repo['setup_command']}` (exit {repo['setup_rc']})."
        )
        out.append("")
        out += _stage_lines("Fresh clone", repo["fresh_clone"])
        out += _stage_lines("After setup", repo["after_setup"])
        out.append("")
        labels = {TRUE: "Right", GAP: "SDETKit gap", ENVIRONMENT: "Environment"}
        out += [f"- {labels.get(kind, kind)}: {text}" for kind, text in _notes(repo["name"])]
        out.append("")
    out += [
        "## Reproduce",
        "",
        "```bash",
        "python scripts/external_repo_proof.py run --workdir /tmp/external-repos",
        "python scripts/external_repo_proof.py render",
        "```",
        "",
        "`run` needs network access to GitHub and the package indexes, plus `uv` and "
        "`poetry` on `PATH`, and rewrites `docs/artifacts/external-repo-proof/results.json`; "
        "`render` rebuilds this page from it. A test keeps the page and the results in step.",
        "",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run")
    run_p.add_argument("--workdir", type=Path, required=True)
    run_p.add_argument("--runner-note", default="")
    render_p = sub.add_parser("render")
    render_p.add_argument("--check", action="store_true")
    ns = parser.parse_args(argv)

    if ns.cmd == "run":
        data = run(ns.workdir, ns.runner_note)
        RESULTS.parent.mkdir(parents=True, exist_ok=True)
        RESULTS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        PAGE.write_text(render(data), encoding="utf-8")
        return 0
    page = render(json.loads(RESULTS.read_text(encoding="utf-8")))
    if ns.check:
        if PAGE.read_text(encoding="utf-8") != page:
            print(f"{PAGE.relative_to(ROOT)} is out of date: run render", file=sys.stderr)
            return 1
        return 0
    PAGE.write_text(page, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
