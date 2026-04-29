# Next 10 Follow-ups

Planned follow-ups to continue polishing the upgrade lane.

1. [x] Automate first-proof artifact retention cleanup with explicit TTL policy. ✅ Implemented via `cleanup-first-proof-artifacts`.
2. [x] Add CI job to publish execution-report.md and upgrade-status-line.txt as artifacts. ✅ Implemented in `.github/workflows/first-proof-artifact-publish.yml`.
3. [x] Add failure taxonomy tags to doctor-remediate outputs for better routing. ✅ Added `tags` field in remediation actions.
4. [x] Track median time-to-remediate from followup-ready history. ✅ Added `followup-ready-metrics` history+median computation.
5. [x] Add weekly trend markdown report for ops-bundle contract pass rate. ✅ Added `first-proof-ops-bundle-trend-report`.
6. [x] Introduce per-branch trend splits (main vs feature branches). ✅ Added branch-aware trend metrics.
7. [x] Add schema versioning + schema contract tests for all new first-proof artifacts. ✅ Added `schema_version` + `first-proof-schema-contract`.
8. [x] Expose `make first-proof-dashboard` to render consolidated summary bundle. ✅ Added dashboard JSON+MD renderer.
9. [x] Add changelog automation for follow-up workflow improvements. ✅ Added `followup-changelog` JSONL automation.
10. [x] Create a release-readiness score threshold gate configurable by profile. ✅ Added `first-proof-readiness-threshold` + profile config.
