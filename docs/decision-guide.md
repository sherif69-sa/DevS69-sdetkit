# Is SDETKit right for your repo? (Decision Guide)

Use this page to make a fast, technical decision: **fit, first path, and stop point**.

SDETKit is a layered **release-confidence and engineering-operations toolkit**. It is strongest when you need deterministic checks, reusable evidence, and a repeatable operator workflow across local and CI usage.

## 1) Good-fit profile

SDETKit is usually a good fit when at least one of these is true:

| Repo/team profile | Why SDETKit fits |
| --- | --- |
| Solo maintainer on a growing repo | You want one repeatable command path instead of remembering scattered scripts and tool flags. |
| Repo owner improving release confidence | You need a clearer go/no-go signal than ad hoc interpretation of multiple tool outputs. |
| QA/SDET/reliability-minded team | You want deterministic, policy-aware checks and consistent evidence artifacts for triage/audits. |
| Team standardizing checks/evidence/CI | You want the same operator workflow locally and in CI, with machine-readable outputs. |
| Advanced operator with broader workflow needs | You want access to a larger command surface (`doctor`, `repo`, `security`, `evidence`, `report`, `ops`) beyond a single gate command. |

## 2) When SDETKit is probably *not* worth it

SDETKit may be unnecessary if:

- Your repo is very small/simple and release risk is low.
- You only want raw underlying tools and prefer to wire everything manually.
- Your team is not willing to adopt an opinionated workflow and shared command conventions.
- You are not ready for a broader command surface beyond a minimal one-off check.

If these apply, run only the lightweight path first (below), then stop unless you see clear repeatability or release-confidence gaps.

## 3) Choose your entry path

Pick one path based on what you need to answer first.

| If you need to... | Start here | Then go to |
| --- | --- | --- |
| Evaluate quickly | `bash scripts/ready_to_use.sh quick` | [Ready-to-use quickstart](ready-to-use.md) |
| Inspect proof/artifacts before adopting | [Evidence showcase](evidence-showcase.md) | [Release confidence](release-confidence.md) |
| Understand capability breadth | [Command taxonomy](command-taxonomy.md) | [CLI reference](cli.md) |
| Adopt in CI with low risk | [Recommended CI flow](recommended-ci-flow.md) | [Adoption guide](adoption.md) |
| Go deeper into broader workflows | [Example adoption flow](example-adoption-flow.md) | [Ops control plane](ops.md) + [Evidence pack](evidence.md) |

## 4) Manual scattered workflow vs SDETKit workflow

A fair comparison for evaluator teams:

| Dimension | Manual scattered workflow | SDETKit workflow |
| --- | --- | --- |
| Command execution | Multiple tools/scripts, order depends on operator memory | Shared command lanes (`quick`, `release`) and CLI gates |
| Output consistency | Mixed formats and ad hoc interpretation | Deterministic pass/fail plus structured evidence outputs |
| Triage speed | Context spread across logs and tool-specific outputs | Standardized command path and artifact-oriented troubleshooting |
| CI portability | Each repo reinvents wiring | Reusable adoption path and recommended CI baseline |
| Repeatability | Varies by engineer and repo maturity | Higher consistency through a defined operator experience |
| Trade-off | Maximum flexibility, more coordination overhead | More opinionated model, broader surface area to learn |

SDETKit does **not** replace every underlying tool; it standardizes how they are orchestrated and interpreted for release-confidence decisions.

## 5) First-time evaluator: do this first, second, third

1. **Run a quick evaluation**
   ```bash
   bash scripts/ready_to_use.sh quick
   ```
2. **Run the stricter release-confidence lane**
   ```bash
   bash scripts/ready_to_use.sh release
   ```
3. **Choose adoption depth**
   - Lightweight CI rollout: [Recommended CI flow](recommended-ci-flow.md)
   - Broader operator workflow: [Example adoption flow](example-adoption-flow.md)

## 6) Proof checklist before adopting

Before standardizing on SDETKit, inspect these pages:

- [Release-confidence model and lanes](release-confidence.md)
- [System-value comparison: why not just separate tools?](why-not-just-tools.md)
- [Representative adoption walkthrough](example-adoption-flow.md)
- [Evidence/artifact showcase](evidence-showcase.md)
- [Capability map and command taxonomy](command-taxonomy.md)
- [Recommended CI baseline](recommended-ci-flow.md)
- [CLI command reference](cli.md)

This sequence is intentional: decision model -> proof -> adoption route -> command depth.

## 7) “Stop here” point (lightweight path)

Stop after the lightweight path if all of the following are true:

- `quick` and `release` already match your confidence needs,
- you do not need broader operator domains right now,
- and your team is not yet ready to standardize the full command surface.

In that case, keep using:

- `bash scripts/ready_to_use.sh quick`
- `bash scripts/ready_to_use.sh release`
- [Recommended CI flow](recommended-ci-flow.md)

Return to broader docs only when coordination overhead, triage inconsistency, or evidence/governance needs increase.
