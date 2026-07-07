# Doctor maintainer flow

This flow describes how a maintainer can read the Doctor bundle before deciding what to do next.

## Step 1: Open the manifest

Start with `doctor-report-manifest.json`. It lists the generated files and their digests.

## Step 2: Read the Markdown report

Open `doctor-report.md` for a human-readable view. Use it to understand the status, primary finding, and recommended proof commands.

## Step 3: Read the JSON report

Open `doctor-report.json` when a structured view is needed for scripts, dashboards, or precise field inspection.

## Step 4: Compare files to the manifest

When exact content matters, compare each file against the digest recorded in the manifest.

## Step 5: Choose the next proof

Use the report's proof commands as the starting point. Prefer focused tests first, then broader repository checks.

## Step 6: Keep the next change small

If the report leads to code or documentation work, keep the next PR focused on one clear surface.
