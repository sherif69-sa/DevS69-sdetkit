# Command surface inventory (stability-aware)

SDETKit's flagship identity remains:

> **Release confidence / shipping readiness for software teams.**

This page is a discoverability map for the current CLI surface. It does not remove or rename commands, and it follows the stability policy in [stability-levels.md](stability-levels.md) plus boundaries from [productization-map.md](productization-map.md).

## Start here (first-time adopters)

Use this order first:

1. **[Stable/Core] Quick confidence**: `sdetkit gate fast`
2. **[Stable/Core] Strict release gate**: `sdetkit gate release`
3. **[Stable/Core] Readiness diagnostics**: `sdetkit doctor --all --json`
4. **[Stable/Core] Security enforcement**: `sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0`
5. **[Playbooks] Guided rollout discovery**: `sdetkit playbooks`

Wrapper equivalents:

- `bash scripts/ready_to_use.sh quick`
- `bash scripts/ready_to_use.sh release`

## Current top-level command inventory by stability level

This is a major-group inventory for navigation clarity (not an exhaustive subcommand reference).

### Stable/Core

Primary release-confidence and shipping-readiness path:

- `gate`
- `doctor`
- `security`
- `evidence`
- `playbooks` (as discovery entrypoint)

Core engineering workflow support with stable day-to-day utility:

- `repo`, `dev`, `maintenance`
- `ci`, `policy`, `report`
- `kv`, `apiget`, `cassette-get`, `patch`

## Integrations

Environment-dependent integration and control-plane families:

- `ops`
- `notify`
- `agent`
- Platform workflow playbooks such as `github-actions-quickstart` and `gitlab-ci-quickstart` (via `sdetkit playbooks`)

## Playbooks

Guided adoption and execution flows (supported, iterative):

- `onboarding`, `onboarding-time-upgrade`
- `weekly-review`, `first-contribution`, `contributor-funnel`, `triage-templates`
- `startup-use-case`, `enterprise-use-case`
- `demo`, `proof`
- `quality-contribution-delta`, `reliability-evidence-pack`
- `faq-objections`, `community-activation`, `external-contribution-push`, `kpi-audit`

Use `sdetkit playbooks` to discover the full current catalog.

## Experimental

Transition-era/advanced lanes retained for compatibility and specialized programs:

- many `dayNN-*` command families
- many `*-closeout` lanes
- cycle closeout families (for example `continuous-upgrade-cycleX-closeout`)

These remain available intentionally, but are not the first stop for new adopters.

## Transition-era command families (how to treat them)

- Treat `dayNN-*` and `*-closeout` as **opt-in experimental lanes**.
- Prefer Stable/Core commands for go/no-go release decisions.
- Use Experimental flows when you explicitly need historical, campaign, or program-phase workflows.
- Validate these lanes in your own CI/environment before relying on them for critical release decisions.

## Practical navigation rules

- If uncertain, start in **Stable/Core**.
- Add **Integrations** when embedding SDETKit into delivery systems.
- Use **Playbooks** for guided rollout and adoption programs.
- Use **Experimental** lanes intentionally and with explicit validation.

## Related references

- [CLI reference](cli.md)
- [Capability map and command taxonomy](command-taxonomy.md)
- [Stability levels (current policy)](stability-levels.md)
- [Productization map](productization-map.md)
