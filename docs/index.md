# DevS69 SDETKit

**From noisy CI evidence to a reviewable decision, a diagnosis, and the exact next command.**

DevS69 SDETKit is a release-confidence CLI for deterministic ship/no-ship decisions with machine-readable evidence. It runs your repository's own checks in its own environment, reduces a failure to the first one that matters, and tells you what to run next. It never applies, merges or dismisses anything for you.

**Primary outcome:** know if a change is ready to ship.

Canonical first path: `python -m sdetkit gate fast` -> `python -m sdetkit gate release` -> `python -m sdetkit doctor`.

!!! info "Which version these docs describe"
    These docs follow `main`, the 2.0.0 release candidate. The latest published package is `sdetkit==1.2.0`. The verdicts, the fix loop (`diagnose run --prove`) and checks that run in the project's own environment are on `main` only until 2.0.0 is released; the [current product delta](current-product-delta.md) lists every difference.

## Get started

=== "Published release (1.2.0)"

    ```bash
    python -m venv .venv && source .venv/bin/activate
    python -m pip install sdetkit==1.2.0
    ```

=== "Release candidate (main)"

    ```bash
    python -m venv .venv && source .venv/bin/activate
    python -m pip install "git+https://github.com/sherif69-sa/DevS69-sdetkit"
    ```

Then, in your repository:

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor --format json --out build/doctor.json
```

Each command writes one JSON artifact that people, bots and CI read the same way. [Start in 5 minutes](start-here-5-minutes.md) walks through the first run.

## One verdict per run

Every run ends in one of four decisions, recorded in the artifact's `verdict.decision`:

| Verdict | Meaning | What to do |
| --- | --- | --- |
| `SHIP` | Every check ran against this repository and passed. | Continue to `gate release`, or ship. |
| `REVIEW` | Nothing blocks, but a person should look first (findings that do not block, or a proven fix waiting for approval). | Read the findings, then decide. |
| `NOT_RUN` | The checks could not run against this repository, for example because the project is not installed in the environment that ran them. Nothing was proven either way. | Run the setup command in `next_action.next_command`, then run the gate again. |
| `NO_SHIP` | A check failed. | Start from `next_action`: the first failure, its file, and the command to reproduce it. |

A failing run names its first failure instead of the loudest wrapper error, and the command to reproduce it:

```text
SDETKit gate fast: NO_SHIP
A check failed.
python: ... (.venv)
[OK] doctor (...) rc=0
[OK] ruff (...) rc=0
[FAIL] pytest (...) rc=1
first failure (test): FAILED tests/test_release_contract.py::test_wheel_smoke
next: python -m pytest -q tests/test_release_contract.py -o addopts=
```

The same fields are in the JSON report's `next_action` card: `classification`, `first_failure`, `affected_file` and `next_command`.

## From a failing gate to a reviewed fix

After a failing `gate fast`, one command diagnoses the failure, proves the narrowest mechanical fix in a throwaway copy of the repository, and writes a decision card. A person approves or rejects it; nothing is applied for you.

```bash
python -m sdetkit diagnose run --prove
python -m sdetkit diagnose decide --card build/sdetkit/remediation-loop/decision-card.json --approve --reviewer <you>
```

See the [remediation loop](remediation-loop.md) and [first-failure triage](first-failure-triage.md).

## Proven on real projects

`gate fast` has been run on seven well-known open-source projects at pinned commits: pallets/itsdangerous, markupsafe and click, python-attrs/attrs, pytest-dev/pluggy, python-poetry/poetry-core and psf/requests. Every fresh clone reads `NOT_RUN` with the setup command it needs; after setup, five read `SHIP` and two read `NO_SHIP` for real failing tests. The [external repository proof](external-repo-proof.md) records every result and how to reproduce it.

## Where to go next

<div class="grid cards" markdown>

-   **Get started**

    [Start in 5 minutes](start-here-5-minutes.md) · [Choose your path](choose-your-path.md) · [Is it a fit?](decision-guide.md)

-   **Operate**

    [First-failure triage](first-failure-triage.md) · [Investigation guide](investigation-operator-guide.md) · [Artifact reference](artifact-reference.md) · [Recommended CI flow](recommended-ci-flow.md)

-   **Adopt in a team**

    [Adopt in your repository](adoption.md) · [Team adoption checklist](team-adoption-checklist.md) · [Real repository adoption](real-repo-adoption.md)

-   **Reference**

    [CLI reference](cli.md) · [Doctor](doctor.md) · [Security gate](security-gate.md) · [Versioning and support](versioning-and-support.md) · [Stability levels](stability-levels.md)

-   **Contribute**

    [Contributing](contributing.md) · [Repository tour](repo-tour.md) · [Docs map](docs-map.md) · [Release process](project/release-process.md)

-   **Safety boundaries**

    [Security hardening](security.md) · [PR automation boundary](pr-automation.md) · [Remediation cookbook](remediation-cookbook.md)

</div>

This page is the product homepage/router: everything a first-time user needs is linked above. Historical and transition-era references remain intentionally secondary to first-time adoption; use the [archive index](archive/index.md) only after the canonical first path is operating.

SDETKit needs Python 3.10 or newer. Use an isolated environment (a virtualenv or `pipx`).
