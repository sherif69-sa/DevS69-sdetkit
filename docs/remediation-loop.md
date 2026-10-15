# Remediation loop

`sdetkit diagnose run` takes saved CI logs, or the failed steps of your latest gate run, and carries each failure through diagnosis, a fix in a throwaway copy, an independent proof and a verifier decision. It never edits your working tree. You get a reviewable patch and a hash-linked record of how it was produced, and you decide whether to apply it.

```bash
# Diagnose and plan only; nothing is executed.
python -m sdetkit diagnose run --log build/ci-logs/lint/ci_log.txt

# Fix in an isolated copy, score the patch, prove it, and verify it.
python -m sdetkit diagnose run --log build/ci-logs/lint/ci_log.txt --prove
```

### Straight from a failing gate

`gate fast` and `gate release` save their latest result, with each step's output, to `.sdetkit/runs/gate-latest.json`. With no `--log`, `diagnose run` reads it and turns every failed step into a log under `<out-dir>/gate-logs/<step>/output.log`. For `gate release`, the failed steps of its nested `gate fast` are used (`gate_fast.pytest`, `gate_fast.ruff`, ...).

```bash
python -m sdetkit gate fast            # fails
python -m sdetkit diagnose run         # why, and the planned fix
python -m sdetkit diagnose run --prove # the fix, proved in a throwaway copy
```

If the latest run passed, there is nothing to diagnose (exit 0). If it was recorded on a different commit than `HEAD`, `diagnose run` refuses and asks you to run the gate again.

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
| Hand the decision to a person | decision card | `decision-card.json`, `decision-card.md` |

Everything is written to `build/sdetkit/remediation-loop/` unless you pass `--out-dir`. `loop.json` summarises the run and lists every artifact.

## RepoMemory

Every run appends its trajectory records to `.sdetkit/memory/trajectories.jsonl` (pass `--memory` to choose the file, `--no-memory` to skip it). Before scoring, the loop reads that history:

- a fix pattern the verifier accepted at least twice is treated as proven, so the patch scorer stops deducting for an unrepeated pattern;
- a failure surface whose fixes the verifier blocked, or people rejected, at least twice is held for review, so later fixes there are blocked.

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

## Decision cards and human decisions

Every run ends with a decision card: one object (`decision-card.json`, `sdetkit.decision_card.v1`) and one PR comment (`decision-card.md`) holding the failure, the SafetyGate decision, the proposed patch (files, line counts, SHA-256), the score and risk flags, the proof and verifier results, whether the protected proof chain still verifies, the RepoMemory context, and the options a person has. `approve` is offered only for a `verified_candidate` whose patch exists and whose chain verifies; `reject` is always offered.

A person records the decision:

```bash
python -m sdetkit diagnose card --loop-dir build/sdetkit/remediation-loop --format md   # rebuild or print the card
python -m sdetkit diagnose decide --card build/sdetkit/remediation-loop/decision-card.json --approve --reviewer sam
python -m sdetkit diagnose decide --card build/sdetkit/remediation-loop/decision-card.json --reject --reviewer sam --note "wrong file"
```

`decide` writes `decision-record.json` (`sdetkit.decision_record.v1`), bound to the card's digest and the patch's SHA-256. It refuses a card edited after it was built, a patch changed on disk, loop artifacts that changed, a proof chain that no longer verifies, and an option the card does not offer. Approving applies nothing: the record names the `git apply` command the person runs, and its verdict is `REVIEW` until CI proves the pushed fix. `verify merge --evidence decision-record.json` reads it like any other verdict. Both decisions are appended to RepoMemory (`human_approved`, `human_rejected`).

### Posting the card on a pull request

The card's Markdown starts with `<!-- sdetkit:decision-card -->` so a CI job can keep one comment up to date. `--prove` runs the repository's own proof commands, so run it where the pull request's code has no write token, and post from a separate job that never checks that code out:

```yaml
# .github/workflows/decision-card.yml: runs on the PR's code, read-only token.
on: pull_request
permissions: { contents: read }
jobs:
  card:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python -m pip install sdetkit ruff pre-commit
      - run: |
          mkdir -p build/ci-logs/lint
          { echo "Run python -m ruff format --check ."; python -m ruff format --check .; } \
            > build/ci-logs/lint/ci_log.txt 2>&1 && exit 0
          python -m sdetkit diagnose run --log build/ci-logs/lint/ci_log.txt --prove --no-memory
      - uses: actions/upload-artifact@v4
        with: { name: decision-card, path: build/sdetkit/remediation-loop/decision-card.md, if-no-files-found: ignore }
```

```yaml
# .github/workflows/decision-card-post.yml: posts only; never checks out PR code.
on:
  workflow_run: { workflows: [decision-card], types: [completed] }
permissions: { actions: read, pull-requests: write }
jobs:
  post:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with: { name: decision-card, run-id: "${{ github.event.workflow_run.id }}", github-token: "${{ github.token }}" }
        continue-on-error: true
      - env: { GH_TOKEN: "${{ github.token }}", GH_REPO: "${{ github.repository }}" }
        run: |
          [ -f decision-card.md ] || exit 0
          pr="${{ github.event.workflow_run.pull_requests[0].number }}"
          gh pr comment "$pr" --body-file decision-card.md --edit-last || gh pr comment "$pr" --body-file decision-card.md
```

The comment is advisory: it changes no check, and every authority flag on the card is `false`. `workflow_run.pull_requests` is empty for pull requests from forks; look those up by `workflow_run.head_sha` instead.

## Boundaries

- Only deterministic, mechanical fixes run: `ruff format` for formatting drift and `ruff check --fix` for fixable lint, and only on the files the SafetyGate allows. Test, type, dependency, security and unknown failures stay review-first.
- The fix runs in a temporary copy; the proof runs in a second copy whose changed-file list comes from git, not from the fixer.
- The worker that applies the fix never certifies it: the protected proof chain records the proof and the verifier as separate stages.
- `automation_allowed`, `patch_application_allowed` and `merge_authorized` are always `false`. Applying the patch is your decision: record it with `diagnose decide`, then `git apply proposed.patch` on a branch.
