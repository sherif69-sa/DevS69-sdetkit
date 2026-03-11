# Is SDETKit right for your repo? (Decision Guide)

Use this page to make a fast decision on fit. Core promise: **deterministic release-confidence checks and evidence-backed shipping decisions**.

If you already know SDETKit is a fit and only need rollout selection, use [Choose your path](choose-your-path.md).

## 1) Good-fit profile

SDETKit is usually a good fit when at least one of these is true:

| Repo/team profile | Why SDETKit fits |
| --- | --- |
| Repo owner improving release confidence | You want deterministic go/no-go checks instead of ad hoc interpretation. |
| QA/SDET/reliability-minded team | You need repeatable checks plus evidence artifacts for triage and audits. |
| Team standardizing local + CI decisions | You want one command path and consistent outputs across environments. |
| Platform/release team with governance needs | You need evidence-backed release approvals with machine-readable outputs. |

## 2) When SDETKit is probably *not* worth it

SDETKit may be unnecessary if:

- Your repo is very small/simple and release risk is low.
- You only want raw underlying tools and prefer fully custom orchestration.
- Your team is not ready to adopt a shared command path.

If these apply, run only the lightweight core lane first, then stop unless repeatability or evidence gaps appear.

## 3) First-time core path (recommended)

Start with the five hero paths:

1. **Install** → [Ready-to-use quickstart](ready-to-use.md)
2. **Gate fast** → `python -m sdetkit gate fast`
3. **Gate release** → `python -m sdetkit gate release`
4. **Doctor** → `python -m sdetkit doctor`
5. **Evidence/report outputs** → [Evidence showcase](evidence-showcase.md), [Reporting and trends](reporting-and-trends.md)

## 4) Manual scattered workflow vs SDETKit workflow

| Dimension | Manual scattered workflow | SDETKit workflow |
| --- | --- | --- |
| Command execution | Multiple tools/scripts with operator-defined order | Core gate path with deterministic outcomes |
| Output consistency | Mixed formats and ad hoc interpretation | Structured evidence and report outputs |
| Release decision quality | Subjective and reviewer-dependent | Evidence-backed and repeatable |
| CI portability | Each repo reinvents wiring | Reusable adoption path and baseline |

SDETKit does **not** replace every underlying tool; it standardizes orchestration and interpretation for release-confidence decisions.

## 5) “Stop here” point (lightweight path)

Stop after the lightweight path if:

- `gate fast` and `gate release` already meet confidence needs,
- doctor checks are healthy,
- and current evidence outputs satisfy release reviewers.

Then keep using the core commands and return to broader docs only when integration or scale needs increase.
