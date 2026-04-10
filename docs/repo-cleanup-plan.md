# Repository cleanup and organization plan

This page defines a practical structure standard for keeping the repository easy to navigate as it grows.

## Objectives

- Make the first 5 minutes in the repo obvious for new contributors.
- Keep top-level files focused on project-wide entrypoints.
- Reduce “where should this file go?” ambiguity.
- Keep generated outputs isolated from hand-maintained source.

## Directory ownership model

| Area | Owned content | Do not place here |
| --- | --- | --- |
| `src/sdetkit/` | product/runtime Python modules | long-form docs, generated logs |
| `tests/` | test logic, fixtures, test helpers | production implementation code |
| `docs/` | user/operator/maintainer documentation | generated runtime outputs |
| `examples/` | sample payloads and walkthrough artifacts | CI logs, one-off debug files |
| `scripts/` | reusable local automation helpers | product business logic |
| `templates/` | reusable document/code templates | ad hoc one-time notes |
| `.sdetkit/` | local generated outputs for workflows | hand-authored docs or code |
| `artifacts/` | generated evidence packs and reports | source-of-truth docs |

## Root-level policy

Keep only project-wide files at repository root.

### Allowed at root

- Core docs: `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `ROADMAP.md`, `RELEASE.md`
- Governance/policy: `LICENSE`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `SUPPORT.md`
- Build/config: `pyproject.toml`, `poetry.lock`, `mkdocs.yml`, `noxfile.py`, `Makefile`
- Entrypoint scripts: `quality.sh`, `ci.sh`, `premium-gate.sh`, `security.sh`

### Prefer moving out of root

- Feature-specific markdown docs → `docs/`
- Temporary scripts → `scripts/` or `tools/`
- Generated JSON/MD evidence → `.sdetkit/out/` or `artifacts/`

## Naming and placement conventions

1. Prefer concise, topic-first filenames (for example `release-readiness.md` over `my-new-release-readiness-notes-v2.md`).
2. Keep docs grouped by intent:
   - `docs/integrations-*` for integration workflows.
   - `docs/*-report*` for generated or periodic reporting narratives.
   - `docs/artifacts/` for sample generated bundles.
3. Match new Python modules with corresponding tests in `tests/`.
4. Link from discovery pages (`README.md`, `docs/index.md`) instead of duplicating context across many root docs.

## Contribution checklist for structure hygiene

Before opening a PR:

- [ ] New files are in the smallest relevant directory scope.
- [ ] Root directory did not gain non-global files.
- [ ] Generated output is not mixed with hand-written source.
- [ ] README and/or docs index includes links for any new user-facing docs.
- [ ] If a folder grows significantly, add or refresh its local orientation doc.

## Suggested ongoing cleanup cadence

- Weekly: scan root for accidental drift.
- Monthly: merge duplicate docs or stale variants into canonical pages.
- Per release: validate that README “start here” links still match active command surfaces.

## Docs drift checklist

Use this quick check before merging documentation edits:

- [ ] Verify every referenced file path exists in the current repository tree.
- [ ] Verify each documented command example still runs (or is clearly marked as illustrative-only).
- [ ] Verify each link target points to the current canonical page/path (not a superseded duplicate).
