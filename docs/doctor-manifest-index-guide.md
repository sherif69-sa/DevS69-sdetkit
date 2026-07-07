# Doctor manifest index guide

The Doctor artifact manifest is the index file for the generated bundle directory.

## Purpose

Use the manifest to discover generated outputs instead of hard-coding every path in downstream tools.

## Expected top-level fields

- `schema_version`
- `report_schema_version`
- `status`
- `outputs`

## Output entries

Each output entry should include:

- `path`
- `sha256`

The path is relative to the artifact directory. The digest lets a maintainer compare the manifest to the generated file content.

## Reading process

1. Parse `doctor-report-manifest.json`.
2. Read the `outputs` object.
3. Resolve each output path relative to the bundle directory.
4. Check that each file exists.
5. Compare the digest when the consumer needs a stable content check.

## Growth rule

New outputs should be added as new entries under `outputs`. Existing entries should keep their meaning so older consumers can continue reading the base report files.
