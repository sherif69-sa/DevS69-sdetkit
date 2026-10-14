# Remediation loop

`sdetkit diagnose run` takes saved CI logs and carries each failure through diagnosis, a fix in a throwaway copy, an independent proof and a verifier decision. It never edits your working tree. You get a reviewable patch and a hash-linked record of how it was produced, and you decide whether to apply it.

```bash
# Diagnose and plan only; nothing is executed.
python -m sdetkit diagnose run --log build/ci-logs/lint/ci_log.txt

# Fix in an isolated copy, score the patch, prove it, and verify it.
python -m sdetkit diagnose run --log build/ci-logs/lint/ci_log.txt --prove
```

## What happens

| Stage | Engine | Artifact |
| --- | --- | --- |
| Extract the first real failure from each log | `diagnose ci-log` (Python, JS/TS, Go, Java, Rust, .NET, C++) | `failed-check-logs.json` |
| Classify the failed checks | `diagnose checks` | `check-intelligence.json` |
| Build diagnostic vectors | `diagnose vector` | `diagnostic-vector.json` |
| Plan a remediation | `diagnose remediation` | `remediation-plan.json` |
| Record the SafetyGate decision | SafetyGate | `failure-vector.json`, `safety-gate.json` |
| Apply the mechanical fix in a throwaway copy (`--prove`) | ruff, limited to the SafetyGate's allowed files | `proposed.patch` |
| Read proven patterns | RepoMemory | `pattern-insights.json` |
| Score the patch | `verify score` | `patch-score.json` |
| Run the plan's proof in a second isolated copy | `verify isolated` | `verification-evidence.json` |
| Verify independently | `verify patch` | `protected-verifier-result.json` |
| Record the attempt | trajectory store and RepoMemory (both append) | `trajectory.jsonl`, `trajectory-summary.json` |
| Report and bind every stage | protected proof chain | `loop-report.md`, `protected-proof-chain.json` |

Everything is written to `build/sdetkit/remediation-loop/` unless you pass `--out-dir`. `loop.json` summarises the run and lists every artifact.

## RepoMemory

Every run appends its trajectory records to `.sdetkit/memory/trajectories.jsonl` (pass `--memory` to choose the file, `--no-memory` to skip it). Before scoring, the loop reads that history:

- a fix pattern the verifier accepted at least twice is treated as proven, so the patch scorer stops deducting for an unrepeated pattern;
- a failure surface whose fixes the verifier blocked at least twice is held for review, so later fixes there are blocked.

History can make the scorer more or less cautious; it never grants authority.

```bash
python -m sdetkit diagnose memory            # records, decisions, proven patterns
python -m sdetkit diagnose memory insights --format json
python -m sdetkit diagnose memory query --decision verified_candidate
```

## Decisions

| Decision | Meaning |
| --- | --- |
| `verified_candidate` | The fix changed only allowed files, its proof passed in isolation, and the verifier accepted it. Review `proposed.patch`. |
| `blocked_review_first` | The fix ran, but the score, the proof or the verifier rejected it. Read `protected-verifier-result.json`. |
| `no_change` | The fix changed nothing in a fresh copy, so the log is stale or the failure is already fixed. |
| `proof_not_run` | A safe candidate exists; rerun with `--prove` to fix and verify it. |
| `review_first` | No failure is eligible for a mechanical fix; the report lists why. |

## Boundaries

- Only deterministic, mechanical fixes run: `ruff format` for formatting drift and `ruff check --fix` for fixable lint, and only on the files the SafetyGate allows. Test, type, dependency, security and unknown failures stay review-first.
- The fix runs in a temporary copy; the proof runs in a second copy whose changed-file list comes from git, not from the fixer.
- The worker that applies the fix never certifies it: the protected proof chain records the proof and the verifier as separate stages.
- `automation_allowed`, `patch_application_allowed` and `merge_authorized` are always `false`. Applying the patch is your decision: `git apply proposed.patch` on a branch.
