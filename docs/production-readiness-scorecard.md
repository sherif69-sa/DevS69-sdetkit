# Production Readiness Scorecard

`python -m sdetkit readiness` provides a deterministic baseline score for investor, operator, and leadership reviews.
It now performs **content-aware checks** (not just file-existence checks) so the output is useful for real release decisions.
The JSON payload includes reviewer-oriented rollups (`check_scorecard`, `failed_checks`, `achievement_level`) and `adaptive_actions` generated from scan evidence (lane + priority + rationale) so teams can quickly see pass/miss posture and changing remediation priorities.
It also includes `scenario_capacity` aligned to a 250-scenario target for scale-phase validation planning, plus `operational_tier` / `top_tier_ready` to signal when the repo is actually ready for top-tier promotion.

## Why this exists

When a team asks "is this platform production-ready?", the answer should be evidence-backed and repeatable.
This scorecard does that by checking for core release-confidence assets and producing a weighted score.

## Usage

```bash
python -m sdetkit readiness . --format text
python -m sdetkit readiness . --format json
```

## Current weighting model (`sdetkit.readiness.v2`)

- Security policy includes vulnerability/reporting language (`SECURITY.md`) — 12
- Release process includes explicit checklist language (`RELEASE.md`) — 12
- Quality playbook includes gate policy language (`QUALITY_PLAYBOOK.md`) — 8
- CI workflow includes tests + lint/quality execution (`.github/workflows/ci.yml`) — 14
- Baseline automated test breadth (`tests/test_*.py` count >= 10) — 10
- Docs entrypoint includes canonical path (`docs/index.md`) — 8
- Dependency reproducibility lockfiles (`requirements.lock` + `poetry.lock`) — 10
- Artifact evidence directory presence (`artifacts/` and/or `docs/artifacts`) — 8
- Governance docs presence (`CODE_OF_CONDUCT.md`, `SUPPORT.md`, `CONTRIBUTING.md`) — 8
- Changelog includes dated release entries (`CHANGELOG.md`) — 10

## Tier semantics

- `excellent` (>= 90): governance and delivery controls are in place and auditable.
- `strong` (>= 75): mostly production-ready, with a small number of remediation tasks.
- `needs-work` (< 75): baseline controls are missing; close top actions before launch.

## Recommended workflow

1. Run the scorecard in CI on every main-branch merge.
2. Track weekly score trends in leadership ops docs.
3. Treat `top_actions` as backlog items with owners and deadlines.
4. Pair this score with `gate release`, `doctor`, and evidence artifacts for final ship/no-ship decisions.

## Review + Doctor integration

- `sdetkit review` now writes `readiness.json` as a first-class artifact for repo-like targets.
- Review payloads include `adaptive_database.readiness_snapshot` (`score`, `tier`, `artifact`) so operator dashboards can query readiness directly from the adaptive database object.
- Adaptive database now carries richer control-plane analytics (`quality_matrix`, `findings_analytics`, `action_analytics`, `scalability_posture`) for large-scale reviewer automation.
- Adaptive database now also carries `release_readiness_contract` to support final-day launch calls (`gate_decision`, blockers, next 24h/72h actions).
- Review outputs now include standalone `adaptive-database.json` so external control planes can ingest adaptive data without parsing full `review.json`.
- Review outputs now include `release-readiness.json` and `release-readiness.md` for release-room decision handoffs.
- Release readiness contracts include traceable metadata (`contract_id`, `generated_at_utc`, `next_review_due_at_utc`) so repeated runs can be tracked during launch week.
- Release readiness contracts also include a `trend` block (`decision_changed`, `blockers_delta`) so operators can track whether launch posture is improving or regressing between runs.
- Release readiness contracts include risk/SLA controls (`risk_score`, `risk_band`, `sla_review_hours`) to prioritize incident-response tempo before cutover.
- Release readiness contracts include `blocker_catalog` entries for structured blocker triage and ownership mapping in release-room workflows.
- Each blocker catalog entry now includes `owner_team` and `response_sla_hours` so action routing is explicit during incident/release huddles.
- Contracts also include `owner_summary` to show blocker load and urgency per team (`blocker_count`, `max_priority`, `min_response_sla_hours`).
- Contracts also include `recommendation_engine` (`now`, `next_72h`, `watchlist`, `owner_routes`) to keep adaptive recommendations aligned with release execution.
- Review also emits `recommendation-backlog.json` with scored backlog rows (`impact_score`, `urgency_score`, `effort_score`, `priority_index`) for delivery ordering.
- Release contracts include `agent_orchestration` recommendations so teams can activate role-specific playbooks/agents when risk or blockers demand deeper response.
- Agent orchestration entries carry `engine_signals` (engine score/status, contradiction cluster count, probe count) to keep agent activation tied to adaptive-review evidence.
- The doctor-first contract sequence now explicitly includes readiness:
  1. `python -m sdetkit doctor --format json`
  2. `python -m sdetkit readiness . --format json`
  3. `python -m sdetkit gate fast --format json --stable-json`
  4. `python -m sdetkit gate release --format json`
  5. `python -m sdetkit review . --format operator-json`
