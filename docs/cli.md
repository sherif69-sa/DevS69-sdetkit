# CLI reference

This page is the **current CLI reference for command discovery** and mirrors the front-door product story: release confidence first, expansion second.

**Primary outcome:** know if a change is ready to ship.

**Canonical first path:** `python -m sdetkit gate fast` → `python -m sdetkit gate release` → `python -m sdetkit doctor`.


## Canonical first-time path (public / stable)

Use this exact sequence first:

1. `python -m sdetkit gate fast`
2. `python -m sdetkit gate release`
3. `python -m sdetkit doctor`

This is the primary product path for first-time adoption and release-confidence proof. If a new visitor remembers only one thing, it should be this exact path.

### What `gate fast` runs in your repository

`gate fast` enforces the policy your repository declares, not SDETKit's own conventions:

| Step | Runs when | Default command |
| --- | --- | --- |
| `doctor` | always | `sdetkit doctor --dev --deps --clean-tree` |
| `ruff`, `ruff_format` | ruff is configured (`[tool.ruff]`, `ruff.toml`, or a pre-commit ruff hook) | `ruff check` / `ruff format --check` on `src` and `tests` (or `.`) |
| `mypy` | mypy is configured (`[tool.mypy]`, `mypy.ini`, or `setup.cfg [mypy]`) | `mypy` with your configured `files`, else `mypy src` |
| `pytest` | tests are detected (`tests/`, `test/`, or pytest config) | `pytest -q` |
| `ci_templates` | opted in | SDETKit CI template validation |

Skipped steps are listed under `skipped_steps` with a reason. Selecting a step with `--only <step>` forces it to run. Override any default in `pyproject.toml`:

```toml
[tool.sdetkit.gate]
pytest_args = ["-q", "tests/smoke"]
mypy_args = ["src"]
ruff_paths = ["src", "tests"]
doctor_args = ["--dev", "--deps", "--clean-tree"]
ci_templates = false

[tool.sdetkit.doctor]
# Optional: require .github/workflows/release.yml to run this tag/version check.
release_tag_check_script = "scripts/check_release_tag_version.py"
```

## Enterprise reliability workflow (step-by-step)

After the canonical path succeeds, use the enterprise doctor profile for stricter release governance and focused remediation loops:

1. Full enterprise scan:
   - `python -m sdetkit doctor --enterprise --format md`
2. Focused failed-check rerun from workspace history:
   - `python -m sdetkit doctor --enterprise-rerun-failed --json`
   - optional scope cap: `--enterprise-rerun-top <N>`
3. Focused high-severity rerun from workspace history:
   - `python -m sdetkit doctor --enterprise-rerun-high --json`
   - optional scope cap: `--enterprise-rerun-top <N>`
4. Repeat rerun/fix cycles until blockers are cleared and score stabilizes.
5. Automation handoff (emit only suggested follow-up pass command):
   - `python -m sdetkit doctor --enterprise-follow-up-only`
   - CI-friendly status mode: `python -m sdetkit doctor --enterprise-follow-up-only --enterprise-follow-up-exit-code`
     (returns exit code `2` when a follow-up pass is recommended, else `0`)
   - plain output emits three lines: command/no-op, `reason: ...`, `alternates: ...`
   - markdown-friendly output: `python -m sdetkit doctor --enterprise-follow-up-only --format md`
   - when no follow-up is needed in markdown mode, output is `_no follow-up pass required_`
   - markdown mode also emits a second line reason hint: `` `reason: <reason>` ``
   - markdown mode also emits a third line alternates hint: `` `alternates: <cmds|none>` ``
   - JSON handoff payload includes `schema_version=sdetkit.doctor.next_pass.v1`
   - JSON handoff payload includes `has_next_pass` boolean for direct pipeline branching
   - JSON handoff payload includes `next_pass_reason` (`none|blockers_present|failed_checks_present`)
   - JSON handoff payload includes `alternate_commands` for fallback lane selection
   - JSON handoff payload includes `exit_code_hint` (`0` no follow-up, `2` follow-up recommended)
   - note: this handoff mode is standalone and cannot be combined with rerun flags.
   - note: `--enterprise-follow-up-exit-code` only works with `--enterprise-follow-up-only`.

If historical workspace payloads do not include per-check severity metadata, `--enterprise-rerun-high` falls back to rerunning recorded failed checks.

Expected enterprise outputs include:

- profile markers (`profile=enterprise`, `profile_mode=full_scan|rerun_failed|rerun_high`)
- rerun scope metadata (`rerun_top`) when `--enterprise-rerun-top` is used
- enterprise execution insights (maturity tier, blockers, optimization queue, follow-up pass reason)
- follow-up command hint (`next_pass_command`) for the recommended focused rerun step
- remediation bundle items for rapid operator follow-up

## Command reference

`python -m sdetkit --help` lists every command. Run `python -m sdetkit <command> --help` for its options.

### Release confidence

| Command | What it does |
| --- | --- |
| `gate` | Run the fast or release quality gate (SHIP / NO-SHIP) |
| `doctor` | Check repository and release readiness |
| `release` | Release kit: release gate|doctor|security|evidence|repo |
| `security` | Scan for secrets and risky code, with a baseline |
| `evidence` | Pack, validate and compare release evidence |
| `report` | Ingest, diff and build run report artifacts |

### Diagnose and adopt

| Command | What it does |
| --- | --- |
| `diagnose` | Diagnosis engine: check intelligence, failure vectors, remediation plans |
| `verify` | Fix-safety checks: protected verifier, patch scoring, benchmarks, merge |
| `investigate` | Diagnose a failure and print the next action |
| `triage-ci` | Diagnose a saved CI job log |
| `mission-control` | Build a release-confidence evidence bundle |
| `adoption-surface` | Map a repository's languages, CI and proof commands (read-only) |
| `adoption-proof-recommendations` | Recommend proof commands from an adoption-surface artifact |
| `adoption-repo-topology` | Map workspace topology from an adoption-surface artifact |
| `fit` | Recommend an adoption depth for a repository |
| `adoption` | Plan follow-up actions from fit and gate results |
| `repo` | Check, fix and audit repository hygiene |
| `init` | Scaffold SDETKit config in a repository |
| `dev` | Developer setup: pre-commit and IDE integration |
| `maintenance` | Run repository maintenance checks |

### SDET utilities

| Command | What it does |
| --- | --- |
| `apiget` | HTTP GET JSON with retries, pagination and cassette record/replay |
| `cassette-get` | Record or replay a single HTTP GET cassette |
| `kv` | Parse key=value input into JSON |
| `patch` | Apply a JSON patch spec to files, with size limits |
| `serve` | Run SDETKit as a local review API service |
| `inspect` | Inspect CSV/JSON evidence and emit diagnostics |
| `inspect-compare` | Compare inspect snapshots for baseline drift |
| `inspect-project` | Run inspection policy packs over dataset families |

### Advanced

| Command | What it does |
| --- | --- |
| `readiness` | Score repository release readiness |
| `release-room` | Build a release-room operator plan |
| `adaptive` | Local adaptive memory: init, ingest, history, explain |
| `ci` | Validate CI workflow templates |
| `policy` | Snapshot, check and diff repository policy |
| `review` | Run the review workflow over a repository |
| `boost` | Scan a repository and rank local risk signals |
| `index` | Build or inspect a local repository index |
| `kits` | List, search and describe the umbrella kits |
| `intelligence` | Flake detection, change impact and failure fingerprints |
| `integration` | Integration checks, environment matrix and cassette validation |
| `forensics` | Failure forensics kit |
| `contract` | Print SDETKit runtime and integration contracts |
| `example` | Run the guided example flow |
| `notify` | Send a message through a notification adapter |
| `ops` | Run, replay and diff operations workflows |
| `workflow-governance-report` | Report on GitHub Actions workflow permissions (read-only) |

### Subcommand groups

`release`, `diagnose` and `verify` take a subcommand and pass the remaining arguments to it. `python -m sdetkit <group> --help` lists them.

#### `release`

| Subcommand | What it does |
| --- | --- |
| `gate` | Run the gate |
| `doctor` | Run doctor |
| `security` | Run the security gate |
| `evidence` | Build or check evidence |
| `repo` | Run repository checks |

#### `diagnose`

`diagnose run` chains the other subcommands end to end; see [Remediation loop](remediation-loop.md).

| Subcommand | What it does |
| --- | --- |
| `run` | Run the full loop on saved CI logs: diagnose, plan, prove in a copy, verify |
| `checks` | Classify failed checks and their provenance |
| `ci-log` | Extract the first failure from a CI log |
| `vector` | Build a diagnostic vector for a failure |
| `plan` | Plan which proofs to run for a failure |
| `job` | Run a full diagnostic job from saved evidence |
| `remediation` | Build a review-first remediation plan |
| `trajectory` | Record a diagnostic worker trajectory |
| `history` | Store and query diagnostic trajectories |
| `security` | Summarise security review evidence |

#### `verify`

| Subcommand | What it does |
| --- | --- |
| `patch` | Verify a candidate patch against protections |
| `score` | Score a candidate patch |
| `benchmark` | Replay a fix benchmark |
| `merge` | Decide merge readiness from evidence |
| `isolated` | Run a proof command in isolation |
| `network` | Check a proof run's network boundary |
| `inventory` | Collect a git file inventory |
### Removed commands

The CLI no longer includes the hidden playbook, closeout, phase and legacy-namespace commands (`playbooks`, `legacy`, `*-closeout`, `phase*`, `start`, `onboarding`, `agent`, `author` and similar) together with `--show-hidden` and `--no-legacy-hint`. Their workflows were reporting-only and are not replaced. `gate release` no longer runs a playbook validation step.

## Adoption surface artifact

Use `adoption-surface` when an operator needs a read-only map of the repository before choosing proof commands or rollout depth.

```bash
python -m sdetkit adoption-surface --root . --out build/sdetkit/adoption-surface.json --format text
```

The command writes a deterministic JSON artifact at `build/sdetkit/adoption-surface.json` by default. It detects repository evidence such as languages, package managers, CI systems, security tools, artifact surfaces, and recommended proof commands.

Safety boundary:

- it does not run the recommended proof commands
- it does not install dependencies
- it does not apply patches
- it does not authorize automation or merge
- the emitted payload keeps `automation_allowed=false`, `merge_authorized=false`, and `semantic_equivalence_proven=false`

Use this artifact as an operator handoff before expanding into CI rollout, investigation, or portfolio automation.

## Contract expectations

Public kit commands are contract-oriented:

- machine-readable JSON with `schema_version`
- deterministic ordering and reproducible artifacts
- stable exit-code lanes (`0` success, `1` policy/contract failure, `2` invalid input/usage)


## Boost Scan Engine (advanced but supported)

`boost scan` is a deterministic local-only repo intelligence surface that ranks important local signals into one concise operator report.

Posture:

- no external services
- no network dependency
- stable machine-readable output via `operator-json`

Recommended first command:

```bash
python -m sdetkit boost scan . --minutes 5 --max-lines 100 --format text
```

Operator JSON contract example:

```bash
python -m sdetkit boost scan . --minutes 5 --max-lines 100 --format operator-json
```

The v1 report (default mode) includes decision, score, top risks, recommended fixes, high-signal files, next PR candidates, and evidence files.

### Boost Scan v2 (adaptive mode)

When `--deep` and/or `--learn` is enabled, Boost Scan switches to adaptive schema `sdetkit.boost.scan.v2`.

- `--deep` builds repo index evidence via the local index engine.
- `--learn` initializes and ingests into local SQLite adaptive memory.
- `--db` sets adaptive DB path (local file, do not commit).
- `--index-out` sets index evidence output location.
- `--evidence-dir` writes `boost-scan.json`, `boost-scan.txt`, `index.json`, and memory evidence files when learning.

Examples:

```bash
python -m sdetkit boost scan . --deep --learn --db .sdetkit/adaptive.db --max-lines 100 --format text
python -m sdetkit boost scan . --deep --learn --db .sdetkit/adaptive.db --format operator-json
python -m sdetkit boost scan . --index-out build/sdetkit-index --evidence-dir build/boost-scan --format operator-json
```

## Related references

- [Command surface inventory (stability-aware)](command-surface.md)
- [Stability levels](stability-levels.md)
- [Versioning and support posture](versioning-and-support.md)
- [Command taxonomy](command-taxonomy.md)
- [Umbrella architecture](architecture/umbrella-kits.md)

### `sdetkit adoption-surface --format report`

Render a Markdown-style operator readiness report while also writing the deterministic adoption-surface JSON artifact:

```bash
python -m sdetkit adoption-surface --root . --out build/sdetkit/adoption-surface.json --format report
```

Use this report for review-first adoption planning. It does not authorize automation, patch application, merging, or semantic-equivalence claims.
