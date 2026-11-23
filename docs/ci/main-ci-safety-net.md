# Main CI safety net

Push and pull-request CI remain the primary checks. GitHub does not start a push workflow when a merge is performed with a repository's `GITHUB_TOKEN`. A green dependency PR can therefore reach main without a new main CI run.

CI also runs hourly at minute17 on the default branch. This independently checks the current main using the same jobs and gates, without another credential or any write permission. Scheduled runs use the default offline test mode. Concurrency remains scoped to the ref, so a new main run cancels an older main run rather than piling up full suites.

This is a safety net, not immediate post-merge delivery. GitHub can delay or drop scheduled runs under load and can disable schedules after prolonged repository inactivity. Keep the push trigger, inspect Actions after a merge, and use CI's existing Run workflow button on main when immediate evidence is needed. A missing or delayed run is not a passing result.

The schedule does not merge PRs, modify branches, change protections, change coverage thresholds, or use the dependency lock token.

Sources:
- https://docs.github.com/en/actions/concepts/security/github_token
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
