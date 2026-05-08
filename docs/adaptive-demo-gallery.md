# Adaptive demo gallery

Use this gallery when you want a quick, reviewer-friendly picture of what the Big-Brain adaptive lane should show in pull requests and release reviews.

The examples are intentionally compact. They demonstrate the expected operator behavior for the top scenario families: stay quiet on green evidence, give precise proof commands for known failures, and keep unknown or risky failures review-first.

## How to generate matching artifacts

```bash
python -m sdetkit.adaptive_diagnosis --log build/ci.log --format json --out build/sdetkit/adaptive-diagnosis.json
python -m sdetkit adaptive learn record build/sdetkit/adaptive-diagnosis.json --proof-passed --fix-accepted --format json
python -m sdetkit adaptive learn summarize --format json > build/sdetkit/adaptive-learning-summary.json
python -m sdetkit adaptive brief \
  --diagnosis build/sdetkit/adaptive-diagnosis.json \
  --learning-summary build/sdetkit/adaptive-learning-summary.json \
  --format comment \
  --out build/sdetkit/adaptive-pr-comment.md
python -m sdetkit adaptive portfolio-rollup build/*/adaptive-diagnosis.json --format md --out build/sdetkit/adaptive-portfolio-rollup.md
```

## PR comment patterns

### 1. Green run — no fake intelligence

```md
### SDETKit release signal

✅ Gate is ship-ready; no adaptive remediation block is present.
```

Use this when the gate is ship-ready and adaptive diagnosis is `clear` or only low-risk `monitor`. The comment should not invent a remediation section when there is no failure signal.

### 2. Safe mechanical issue — scoped safe-fix path

```md
### SDETKit adaptive handoff

- Gate: `needs_fix`
- Adaptive status: `needs_fix`
- Primary: `PRE_COMMIT_FORMAT_DRIFT` — Pre-commit formatting drift detected
- First proof: `PYTHONPATH=src python -m ruff format --check tests/test_widget.py`

**Safe-fix status**
- Scoped safe-fix path is available, but only after guardrails and proof artifacts pass.

**Next owner action**
- Run the scoped format fix, re-run the proof command, and attach the updated diagnosis artifact.
```

Use this for narrow mechanical fixes only, such as format drift or safe Ruff import cleanup. Unknown failures must never be routed here.

### 3. Unknown failure — review-first candidates

```md
### SDETKit adaptive handoff

- Gate: `needs_fix`
- Adaptive status: `needs_fix`
- Primary: `UNKNOWN_REVIEW_REQUIRED` — Failure-like evidence needs human review
- Candidate scenarios: `PACKAGE_INSTALL_FAILURE,RUNTIME_EXCEPTION,CACHE_ARTIFACT_POISONING`
- First proof: `python -m pip install -r requirements-test.txt -e .`

**Safe-fix status**
- Review-first: this evidence is not approved for automatic remediation.

**Next owner action**
- Start with the first proof command, confirm the matching scenario, then record whether the proof passed or failed.
```

Use this when logs contain failure-like signals but no known safe remediation path.

### 4. Recurring scenario — learning calibration visible

```md
### SDETKit adaptive handoff

- Gate: `needs_attention`
- Adaptive status: `needs_attention`
- Primary: `KNOWN_ADAPTIVE_PATTERN_AVAILABLE` — Adaptive memory has reusable context
- Candidate scenarios: `RELEASE_VERSION_CONFLICT,CACHE_ARTIFACT_POISONING`
- Calibration: `RELEASE_VERSION_CONFLICT:promote_and_increase_risk:confidence_delta=2:risk_delta=12`
- First proof: `git tag --points-at HEAD`

**Safe-fix status**
- Review-first: this evidence is not approved for automatic remediation.

**Next owner action**
- Compare the current release artifact with prior accepted diagnosis events before changing release metadata.
```

Use this when learning summary data has promoted or demoted candidates based on prior proof/fix outcomes.

## Top scenario review checklist

| Scenario family | What reviewers should see first | Proof command pattern | Automation posture |
| --- | --- | --- | --- |
| `PYTEST_BEHAVIOR_REGRESSION` | First failing test node and assertion summary. | `PYTHONPATH=src python -m pytest -q tests/path.py::test_name` | Human review; code behavior changed. |
| `PYTEST_COLLECTION_IMPORT_FAILURE` | Import traceback and missing module or symbol. | `PYTHONPATH=src python -m pytest -q tests/path.py` | Human review unless environment-only dependency is proven. |
| `RUFF_FORMAT_DRIFT` | File list from format check. | `PYTHONPATH=src python -m ruff format --check <files>` | Safe only for scoped formatting. |
| `RUFF_LINT_CONTRACT` | Ruff rule codes and affected files. | `PYTHONPATH=src python -m ruff check <files>` | Safe only for allowlisted mechanical rules. |
| `MYPY_CONTRACT_DRIFT` | First typed API mismatch and owning module. | `PYTHONPATH=src python -m mypy <module-or-package>` | Human review; type contract may reveal design drift. |
| `COVERAGE_GATE_REGRESSION` | Threshold delta and missed file/package. | `PYTHONPATH=src python -m pytest --cov` | Human review; decide test or threshold response. |
| `PACKAGE_INSTALL_FAILURE` | Resolver/build error, missing extra, or script failure. | `python -m pip install -r requirements-test.txt -e .` | Review-first; environment and dependency state matter. |
| `CACHE_ARTIFACT_POISONING` | Cache key, stale artifact hint, or mismatch after restore. | `python -m pytest -q --cache-clear` | Review-first; clear/rebuild before code changes. |
| `DOCS_BUILD_CONTRACT` | Broken link, strict MkDocs warning, or missing page. | `NO_MKDOCS_2_WARNING=1 python -m mkdocs build -q` | Human review unless link target is obvious and local. |
| `RELEASE_VERSION_CONFLICT` | Tag/version mismatch or duplicate artifact version. | `git tag --points-at HEAD` and `python -m build --sdist --wheel` | Review-first; release metadata changes are high impact. |

## Portfolio rollup interpretation

A portfolio rollup should answer three leadership questions:

1. **Which scenario family is hurting the most repos?** Check `top_risk_scenarios[].repo_count`.
2. **Which repo blocks release signoff?** Check `needs_fix_repos` and `recurrence_by_repo[].max_status`.
3. **What should the owner do next?** Use `next_owner_action` as the release-room handoff sentence.

Example compact output:

```text
schema_version=sdetkit.adaptive.portfolio_rollup.v1
ok=false
recommendation=NO_SHIP
repo_count=3
artifact_count=3
portfolio_risk_score=100
scenario=PYTEST_BEHAVIOR_REGRESSION|risk=82|repos=2
next_owner_action=Block release signoff for api; start with top scenario PYTEST_BEHAVIOR_REGRESSION.
```

## Real-world operator guidance contract

Adaptive diagnosis output is intended to explain a real observed failure, not emit random fixed advice. Each diagnosis now includes `operator_guidance` with:

- `what_is_going_on` — the interpreted failure contract;
- `what_to_fix_first` and `how_to_fix` — the first concrete repair lane;
- `how_to_verify` — proof commands to rerun;
- `automation_boundary` — whether the lane is safe mechanical automation or review-first no-mutation;
- `observed_failure_lines` — sanitized lines from the current log that triggered the diagnosis;
- `why_this_is_not_random` — the traceability statement tying guidance to current evidence.

Unknown, product-risk, or non-mechanical failures stay review-first. Only narrow mechanical lanes such as formatter drift and safe Ruff F401/I001 fixes may be marked safe after proof.

## Real-world scenario database scale

The adaptive database is no longer a tiny fixed set of examples. It combines a curated scenario pack with a deterministic generated failure matrix covering pytest, collection/import failures, Ruff, format drift, mypy, coverage, package managers, docs, Git, CI, network, runtime, cache, release, security, and artifact/dashboard families across operating systems, runners, architectures, network modes, and symptoms. The runtime payload reports `scenario_database.curated_scenario_count`, `generated_matrix_scenario_count`, `total_scenario_count`, and `odds_space_size` so operators can see the actual search space used for candidate matching.

This does not mean the tool auto-fixes everything. The larger database improves matching and guidance; automation remains limited to proven narrow mechanical fixes.
