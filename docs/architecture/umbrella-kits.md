# Umbrella architecture: SDETKit kits

SDETKit exposes one unified umbrella with four kits:

- **Release Confidence Kit** (`sdetkit release ...`)
- **Test Intelligence Kit** (`sdetkit intelligence ...`)
- **Integration Assurance Kit** (`sdetkit integration ...`)
- **Failure Forensics Kit** (`sdetkit forensics ...`)

## Public-surface policy

- Umbrella kits are the primary discovery and documentation surface.
- Legacy direct commands remain stable compatibility aliases.
- Supporting utilities are intentionally secondary in help/docs.

## Contracts and determinism

Kit commands emit deterministic machine-readable outputs with explicit `schema_version`, stable ordering, and exit code contracts.

## Upgrade blueprint model

`sdetkit kits blueprint --goal "..."` now emits a fuller operating model for umbrella upgrades:

- **architecture layers** — experience surface, AgentOS control plane, and deterministic artifact plane,
- **operating model** — discovery, execution, and review cadences for recurring adoption,
- **upgrade backlog** — prioritized upgrade themes such as umbrella routing, AgentOS promotion, topology assurance, and upgrade-audit integration,
- **metrics** — high-signal operating measures such as routing accuracy, artifact coverage, and AgentOS run success rate.

That turns the umbrella architecture from a static catalog into an execution-ready blueprint for teams that want to scale the repo as a product surface instead of a loose collection of commands.

`sdetkit kits optimize --goal "..."` extends that blueprint into a repo-aware alignment plan. It inspects whether doctor, `quality.sh`, premium gate, integration topology fixtures, CI helpers, AgentOS templates, and reproducibility assets are present, then emits:

- an **alignment matrix** for doctor / quality gate / premium gate / topology / AgentOS readiness,
- a **doctor lane** with the recommended readiness command for the current upgrade goal,
- an **auto-fix lane** that promotes premium-gate intelligent remediation before the main merge bar reruns,
- a **quality gate lane** that sequences `quality.sh`, premium gate, and CI in one plan,
- an **integration lane** that keeps topology proof wired into the umbrella,
- a **doctor-quality contract** that keeps promotion and remediation commands in one place,
- an **innovation opportunities** section that recommends the highest-leverage new additions the repo could productize next from dependency, validation, and adapter signals,
- and **performance boosters** that highlight reusable fast-path assets such as pinned CI constraints and gate snapshots.

This makes the umbrella architecture operationally opinionated instead of merely descriptive: the repo can now tell you not just which kit to use, but how to align the major control loops into one upgrade motion.

`sdetkit kits expand --goal "..."` builds one layer further on top of optimize. It converts the repo-aware signals into:

- **feature candidates** — prioritized additions that are concrete enough to implement next,
- **search missions** — targeted discovery prompts for the highest-value follow-up work,
- **rollout tracks** — a now / next / later sequence so expansion work does not become an unbounded idea pile.

That gives maintainers an explicit "what new thing should we build next?" surface instead of requiring them to infer it from the broader optimize payload.

## Compatibility and migration

Use `docs/migration-compatibility-note.md` for migration guidance and the current experimental summary.
