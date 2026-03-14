# DevS69 SDETKit

<div class="quick-jump" markdown>

[⚡ Fast start](#fast-start) · [🧭 Repo tour](repo-tour.md) · [📈 Top-10 strategy](top-10-github-strategy.md) · [🤖 AgentOS](agentos-foundation.md) · [🍳 Cookbook](agentos-cookbook.md) · [🛠 CLI commands](cli.md) · [🩺 Doctor checks](doctor.md) · [🤝 Contribute](contributing.md) · [📦 Legacy reports](#legacy-reports)

</div>

DevS69 SDETKit is a platform for:

1. **release decision-making**
2. **deterministic evidence**
3. **test intelligence**
4. **integration assurance**
5. **failure forensics**

The first 30-second path is the flagship kit surface, not generic utilities.

## Fast start

## Start with flagship kits

- [Release Decision Kit](kits/release-confidence.md)
- [Test Intelligence Kit](kits/test-intelligence.md)
- [Integration Assurance Kit](kits/integration-assurance.md)
- [Failure Forensics Kit](kits/failure-forensics.md)

## Primary operator flow

1. `sdetkit release gate release`
2. `sdetkit release doctor`
3. `sdetkit release security scan`
4. `sdetkit release evidence pack`
5. `sdetkit forensics compare --from <prev> --to <current>`

## Supporting surfaces (demoted)

Utility commands such as `kv`, `apiget`, and `cassette-get` remain available for compatibility and composition, but are intentionally secondary in product positioning.

## Legacy reports

### Top journeys

- Run first command in under 60 seconds
- Validate docs links and anchors before publishing
- Ship a first contribution with deterministic quality gates

### Latest continuous-upgrade lane

- [Cycle 8 big upgrade report](continuous-upgrade-cycle8-big-upgrade-report.md)
- [Continuous upgrade impact #8 closeout](integrations-continuous-upgrade-cycle8-closeout.md)
- [Upgrade implementation research and recommendations](upgrade-implementation-research.md)
