# Adoption fixture OSV policy

Linked issue: #1678.

The `tests/fixtures/adoption_repos/` directories are detector fixtures used by
the adoption-surface and project-discovery test suite. They are not shipped
runtime dependencies, release artifacts, or executable production projects.

The repository-level OSV workflow scans recursively from the repository root and
uploads SARIF to GitHub Code Scanning. Without fixture-local policy files, OSV
reports vulnerabilities from these demo manifests as repository security alerts.

Each affected fixture directory carries its own `osv-scanner.toml` so the
exception stays local to the fixture directory. This keeps root/package
dependency scanning active while preventing fixture-only manifests from
dominating the GHAS backlog.

This policy does not dismiss production alerts, does not weaken root
dependency scanning, and does not change workflow permissions.
