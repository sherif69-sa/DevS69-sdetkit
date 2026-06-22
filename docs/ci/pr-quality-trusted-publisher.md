# PR Quality trusted publisher boundary

## Purpose

PR Quality evidence is produced in the untrusted `pull_request` execution domain with read-only
permissions. Comment publication is performed by a separate `workflow_run` workflow loaded from
the default branch.

## Trust domains

```text
pull_request / PR Quality Comment
  -> read-only GitHub permissions
  -> repository checkout and diagnostic execution
  -> full evidence artifact
  -> minimal publisher handoff artifact

workflow_run / PR Quality Publisher
  -> trusted default-branch workflow definition
  -> no checkout
  -> no setup-python action
  -> no repository module or shell execution
  -> exact run, PR, and head binding
  -> current PR head revalidation
  -> path allowlist, symlink rejection, size and SHA-256 verification
  -> comment publication only
```

## Minimal handoff schema

The handoff contains exactly:

- `manifest.json`
- `payload/pr-comment-body.md`
- `payload/pr-comment-metadata.json`
- `payload/pr-review-summary.md`

The publisher rejects stale heads, closed PRs, unknown paths, symlinks, digest mismatches, unsafe
control characters, active HTML, JavaScript URLs, and oversized bodies. User mentions are
neutralized before publication.

## Authority boundary

The handoff and published report are advisory. They do not authorize patch application, security
dismissal, merge, or claims of semantic equivalence.

## Rollout

The publisher workflow cannot execute from the introducing PR branch because `workflow_run`
loads the workflow from the default branch. Static contract tests and repository proof validate
this PR. The next PR provides the first live end-to-end publisher observation.
