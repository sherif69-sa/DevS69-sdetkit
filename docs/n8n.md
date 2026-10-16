# n8n integration (pull request webhook automation)

The [SDETKit gate action](gate-action.md) posts the verdict on a pull request from GitHub Actions. To run the same flow from n8n instead:

1. Send GitHub `pull_request` webhook events to an n8n Webhook node.
2. Have n8n start a runner or container job that checks out the pull request head and runs:

   ```bash
   python -m pip install sdetkit
   python -m pip install -e ".[test]"   # however your project installs its tests' dependencies
   python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json --summary-out build/gate-summary.md
   ```

3. Post the result back with the GitHub API:
   - a commit status or check run whose state follows `verdict.decision` in `build/gate-fast.json` (`SHIP` and `REVIEW` pass; `NOT_RUN` and `NO_SHIP` fail);
   - a pull request comment with the contents of `build/gate-summary.md`.

## Payload

Include the pull request number, the repository owner and name, the head SHA, and a link to the job's logs in the status and the comment.
