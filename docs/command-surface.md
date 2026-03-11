# Command surface inventory (stability-aware)

SDETKit's flagship identity remains:

> **Release confidence / shipping readiness for software teams.**

This page is a discoverability map for the current CLI surface. It does not remove or rename commands, and it follows the stability policy in [stability-levels.md](stability-levels.md) plus boundaries from [productization-map.md](productization-map.md).

## Command-family contract snapshot

This compact table is sourced from `src/sdetkit/public_surface_contract.py` and covers major command families only.

<!-- BEGIN:PUBLIC_SURFACE_CONTRACT_TABLE -->

| Command family | Purpose | Stability tier | First-time adopter default? | Transition-era / legacy-oriented? |
|---|---|---|---|---|
| `stable-core-release-confidence` | Primary release-confidence and shipping-readiness go/no-go path. | Stable/Core | Yes | No |
| `stable-core-engineering-workflows` | Stable day-to-day engineering and repository utility workflows. | Stable/Core | Yes | No |
| `integrations` | Environment-dependent connectors and delivery-system extensions. | Integrations | No | No |
| `playbooks` | Guided adoption and rollout lanes for operational outcomes. | Playbooks | Yes | No |
| `experimental-transition-lanes` | Transition-era and legacy-oriented lanes retained for compatibility. | Experimental | No | Yes |

<!-- END:PUBLIC_SURFACE_CONTRACT_TABLE -->

Maintainer sync:

- Regenerate this table with `python tools/render_public_surface_contract_table.py`.
- Use `python tools/render_public_surface_contract_table.py --check` in CI/pre-commit to keep docs and contract aligned.

## Recommended starting points (first-time adopters)

For release confidence and shipping readiness, start with the core path first:

1. **Quick confidence gate (Stable/Core):** `sdetkit gate fast`
2. **Strict release gate (Stable/Core):** `sdetkit gate release`
3. **Readiness diagnostics (Stable/Core):** `sdetkit doctor --all --json`
4. **Security enforcement (Stable/Core):** `sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0`
5. **Guided rollout catalog (Playbooks):** `sdetkit playbooks`

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

## Public surface contract (source of truth)

The major command-family contract is defined in:

- `src/sdetkit/public_surface_contract.py`

Maintainer guidance:

- Keep this contract focused on **major top-level families only** (not every subcommand).
- Update this contract first when a family-level productization decision changes (role, stability tier, first-time recommendation, or transition-era/legacy posture).
- Keep CLI/docs discoverability text aligned by sourcing summary text from this contract where practical.

## Related references

- [CLI reference](cli.md)
- [Capability map and command taxonomy](command-taxonomy.md)
- [Stability levels (current policy)](stability-levels.md)
- [Productization map](productization-map.md)
