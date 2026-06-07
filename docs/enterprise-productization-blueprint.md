# AgentOS productization blueprint

## Scope
This blueprint defines how to package the **AgentOS + template engine + omnichannel server** into an enterprise-ready offering with deterministic artifacts, repeatable governance controls, and operational handoff guidance.

## Deployment modes

### 1) Local-only mode
- Execution model: developers and QA teams run `sdetkit` inside their repositories.
- Control plane: none; no central API required.
- Data path: `.sdetkit/` stays in-repo or on local workstation storage.
- Best fit: regulated teams with strict source-code locality requirements.
- Operational deliverables:
  - standardized `sdetkit agent example --scenario repo-enterprise-audit` smoke check
  - local runbooks for template and dashboard generation
  - workstation onboarding and deterministic cache policies

### 2) Server mode
- Execution model: `sdetkit agent serve` hosted in a private network segment.
- Control plane: REST channel adapters (Slack/Telegram simulation + webhook ingress).
- Data path: artifact roots mapped to dedicated storage classes (workspace, history, dashboards).
- Best fit: shared platform teams, internal enablement groups, and multi-team rollouts.
- Operational deliverables:
  - network boundary diagram and ingress policy
  - service account and token management matrix
  - retention policy for conversation logs, run history, and audit artifacts

## Data ownership and controls
- **Ownership default**: customer owns all generated files, logs, and dashboards.
- **Storage boundaries**:
  - run history: `.sdetkit/agent/history/`
  - dashboard artifacts: `.sdetkit/agent/workdir/` or scenario-specific outputs
  - templates and packs: repository `templates/automations/`
- **Controls**:
  - write allowlists for filesystem actions
  - shell allowlists for command execution
  - provider selection (`none` for deterministic offline workflows)
  - deterministic, atomic artifact writes for dashboard/export outputs

## Governance and auditability
- Deterministic run records with stable hashes enable replay validation.
- Agent dashboard summarizes:
  - run count and success rate
  - top templates and top actions
  - failed runs with timestamps and hashes
- Export channels:
  - dashboard output formats: `json`, `md`, `html`, `csv`
  - history summary export: `sdetkit agent history export --format csv`
- Recommended governance bundle:
  - weekly dashboard snapshot (HTML + Markdown)
  - CSV exports attached to audit evidence tickets
  - template pack checksum archive per release

## Enterprise adoption path

### Baseline readiness: Pilot (1-2 squads)
- Baseline templates activated.
- Provider pinned to `none`.
- Dashboard cadence: per pull request and nightly.

### Release readiness: Platform alignment
- Shared template catalog governance owners assigned.
- Omnichannel ingress and rate-limits enabled in controlled channels.
- Role-based operational runbooks published.

### Platform readiness: Program rollout
- Workspace bootstrap scripted with example scenario for acceptance testing.
- Dashboard and export artifacts integrated into quality gates.
- Standardized policy exceptions and waiver process formalized.

## Packaging examples (agency / micro-SaaS)

### Agency package: Managed enablement
- Deliverables:
  - repository bootstrap and policy baseline
  - 8 curated templates aligned to client SDLC
  - omnichannel server deployment and hardening playbook
  - dashboard/report governance SOP and handoff session
- Commercial model: fixed setup fee + monthly operations retainer.

### Micro-SaaS package: Managed platform
- Deliverables:
  - hosted server mode with tenant-isolated workspaces
  - template catalog updates and semantic version channel
  - scheduled dashboard generation + CSV exports to customer bucket
  - quarterly governance evidence pack (runs, failures, controls)
- Commercial model: per-tenant platform fee + usage tier based on run volume.
