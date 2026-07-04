# Pages deployment recovery guide

This guide is for operators triaging `.github/workflows/pages.yml` when the
GitHub Pages build succeeds but the deployment status later fails.

It is review-first guidance. It does not authorize permission reduction,
workflow mutation, merge, or automatic retry loops.

## Failure signature

Treat the failure as deployment-stage when the run shows this sequence:

1. The MkDocs build step completed successfully.
2. `actions/upload-pages-artifact` uploaded the `github-pages` artifact.
3. `actions/deploy-pages` found the artifact metadata.
4. A Pages deployment was created for a concrete commit SHA.
5. The final Pages status poll returned a deployment failure.

This is different from a documentation build failure, broken link, missing
artifact, or token-permission failure.

## First response

Use this order before changing workflow YAML:

1. Confirm the failing run targets the current `main` commit.
2. Confirm the artifact was created in the same workflow run.
3. Confirm `.github/workflows/pages.yml` still grants `pages: write` and
   `id-token: write`.
4. Re-run only the failed deployment job or failed workflow run when the failure
   is isolated to deployment status polling.
5. If the same deployment-stage failure repeats, collect the run id, deployment
   commit SHA, artifact id, and final status message for human review.

## Signals that should not trigger a workflow patch alone

- A Node runtime deprecation warning that does not fail the step.
- A single `Deployment failed, try again later` result after artifact upload.
- A historical pre-merge PR check after the PR has already merged.
- A failure tied to an older merge commit while the current PR head checks are
  green.

## Escalation criteria

Open a workflow-change PR only when repeated evidence shows the workflow itself
is at fault, such as:

- Pages permission errors after deployment creation is attempted.
- Missing artifact despite a successful build step.
- Build output path drift from `site`.
- Repeated deployment failures across fresh reruns and new commits.

## Local proof before escalation

Run the local docs build path before proposing workflow changes:

```bash
python -m pip install -c constraints-ci.txt -r requirements-docs.txt -e .
python scripts/check_public_surface_alignment.py
NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict
```

If local proof passes and the artifact upload step passes, treat the remaining
failure as hosted Pages deployment evidence, not local documentation evidence.
