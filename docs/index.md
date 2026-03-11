<div class="hero-panel" markdown>

<div class="hero-badges" markdown>

<span class="pill">Release-confidence focused</span>
<span class="pill">Deterministic by design</span>
<span class="pill">Audit-friendly outputs</span>

</div>

# DevS69 SDETKit

SDETKit is a release confidence toolkit for SDET, QA, and DevOps teams that need a repeatable answer to: **"is this repo ready to ship?"**

<div class="hero-actions" markdown>

[Start in 5 minutes](#fast-start){ .md-button .md-button--primary }
[Decision guide](decision-guide.md){ .md-button }
[Choose your path](choose-your-path.md){ .md-button }
[Open quickstart](ready-to-use.md){ .md-button }
[Release confidence story](release-confidence.md){ .md-button }
[Adopt in your repo](adoption.md){ .md-button }
[Adoption examples](adoption-examples.md){ .md-button }
[Adoption troubleshooting](adoption-troubleshooting.md){ .md-button }
[First-failure triage](first-failure-triage.md){ .md-button }
[See integrations](github-action.md){ .md-button }
[Extension boundary](integrations-and-extension-boundary.md){ .md-button }
[See playbooks](global-production-transformation-playbook.md){ .md-button }
[See examples](examples.md){ .md-button }
[See evidence commands](evidence.md){ .md-button }

</div>

</div>

## Fast start

### Start here: Stable/Core release-confidence path

New to SDETKit? Use this order for the first run:

1. Install SDETKit from source or GitHub URL (see [ready-to-use.md](ready-to-use.md)).
2. Verify CLI availability (see [Verify your install](ready-to-use.md#verify-your-install)).
3. Run the flagship workflow below (`quick` then `release`).

Run the flagship workflow:

```bash
bash scripts/ready_to_use.sh quick
```

Then run the stricter release gate:

```bash
bash scripts/ready_to_use.sh release
```

### What happens

1. Bootstrap a local environment.
2. Validate CLI health.
3. Run CI-style checks.
4. (Release mode) enforce security policy budgets and run the release gate.

### What proves value quickly

You get deterministic pass/fail output and a clear go/no-go signal you can reuse in local and CI workflows.

## Core path (recommended first-time sequence)

Use this sequence to keep rollout focused:

1. **Quick confidence** via `bash scripts/ready_to_use.sh quick`
2. **Strict release gate** via `bash scripts/ready_to_use.sh release`
3. **Discover core commands** via [cli.md](cli.md)
4. **External adoption** via [adoption.md](adoption.md)
5. **Pick a rollout scenario** via [choose-your-path.md](choose-your-path.md)
6. **See full scenarios** via [adoption-examples.md](adoption-examples.md)

## Flagship workflow (manual form)

```bash
bash ci.sh quick --skip-docs
bash quality.sh cov
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0
python -m sdetkit gate release
```

## Where integrations and playbooks fit

- **Integrations (after core gates):** [GitHub Action](github-action.md), [Recommended CI flow](recommended-ci-flow.md), and [Adopt in your repository](adoption.md).
- **Playbooks (guided rollout):** [Global production transformation playbook](global-production-transformation-playbook.md), [First contribution quickstart](first-contribution-quickstart.md), and [Release-confidence examples](examples.md).
- **Reference depth:** [CLI](cli.md), [Command surface inventory](command-surface.md), and [Capability map](command-taxonomy.md).

## Stability levels

SDETKit documents command and workflow maturity with four levels: **Stable/Core**, **Integrations**, **Playbooks**, and **Experimental**.

- **Stable/Core** is the default production path for release confidence and shipping readiness.
- **Integrations** extend core workflows into CI, notifications, and external systems.
- **Playbooks** provide guided rollout lanes for adoption and operating practice.
- **Experimental** includes transition-era/advanced day and closeout lanes; keep as opt-in with validation.

Read the policies: [stability-levels.md](stability-levels.md) and [versioning-and-support.md](versioning-and-support.md)

Boundary guidance: [integrations-and-extension-boundary.md](integrations-and-extension-boundary.md)

## Next steps (ordered by default path)

- [Decision guide: is SDETKit right for you?](decision-guide.md)
- [Choose your path: compact rollout self-selection](choose-your-path.md)
- [Ready-to-use quickstart](ready-to-use.md)
- [Release confidence model and lanes](release-confidence.md)
- [Versioning and support posture](versioning-and-support.md)
- [Integrations and extension boundary](integrations-and-extension-boundary.md)
- [Adopt in your repository](adoption.md)
- [Recommended CI flow (baseline)](recommended-ci-flow.md)
- [Global production transformation playbook](global-production-transformation-playbook.md)
- [Release-confidence examples](examples.md)
- [Full command reference](cli.md)
- [Command surface inventory (stability-aware)](command-surface.md)
- [Capability map and command taxonomy](command-taxonomy.md)
- [Transition-era historical reports (secondary)](#legacy-reports)

<div class="quick-jump" markdown>

### Top journeys

- Run first command in under 60 seconds
- Validate docs links and anchors before publishing
- Ship a first contribution with deterministic quality gates

- [⚡ Fast start](#fast-start)
- [🛠 CLI commands](cli.md)
- [✅ Verify install first](ready-to-use.md#verify-your-install)
- [🩺 Doctor checks](doctor.md)
- [🤝 Contribute](contributing.md)
- [🧭 Repo tour](repo-tour.md)
- [📦 Legacy reports](#legacy-reports)

</div>

## Legacy reports

Historical day-by-day upgrade reports remain available as transition-era context for audit trails and prior initiatives. They are intentionally secondary to the Stable/Core release-confidence journey.
