# Public release verification records

This page is the repository's **post-release credibility log**.

Use it only for real, completed verification runs after a tag is published and the release artifacts are independently verified. Do not pre-fill this page with hypothetical results.

## Status

The current verified public release is `v1.2.0`.

## v1.2.0 — 2026-07-18

- Package/version verified: `sdetkit==1.2.0`
- Tag: `v1.2.0`
- Source SHA: `5165a82f8cd2ab3ce6be29737a2afdad58ea85a5`
- Verifier: `sherif69-sa`
- Independent environment:
  - OS: WSL Linux
  - Python: 3.10
  - Installer: pip version was not captured in the retained terminal output
- Release workflow run: `29619221288`
- PyPI publication: Trusted Publishing succeeded
- GitHub provenance: succeeded
- Exact-wheel qualification: Python 3.10, 3.11, and 3.12 succeeded

Install and verification commands run:

```bash
python3 -m venv /tmp/sdetkit-1.2.0-release-recovery/venv
/tmp/sdetkit-1.2.0-release-recovery/venv/bin/python -m pip install \
  --no-cache-dir \
  --index-url https://pypi.org/simple/ \
  "sdetkit==1.2.0"
/tmp/sdetkit-1.2.0-release-recovery/venv/bin/python -m sdetkit --help
/tmp/sdetkit-1.2.0-release-recovery/venv/bin/python -m pip show sdetkit
```

Public distribution verification:

| File | SHA-256 |
|---|---|
| `sdetkit-1.2.0-py3-none-any.whl` | `1686c1ea8fc17748ed30bec1a8c7a2b79e2c1f714a6918f9b97647d2f5369b96` |
| `sdetkit-1.2.0.tar.gz` | `e6e1759a8e7c716ea4a6c51f50aa16d422caa56ce9ff218c073056c4b3c2eea9` |

The public PyPI JSON filenames and hashes matched the immutable release manifest exactly. The clean environment installed `sdetkit==1.2.0`, `python -m sdetkit --help` exited successfully, and `pip show` reported `Version: 1.2.0`.

Release references:

- PyPI: <https://pypi.org/project/sdetkit/1.2.0/>
- GitHub Release: <https://github.com/sherif69-sa/DevS69-sdetkit/releases/tag/v1.2.0>
- Source tag: <https://github.com/sherif69-sa/DevS69-sdetkit/tree/v1.2.0>

### Recovery note

The release workflow published the exact distributions successfully, but its first post-publish verification attempt failed before contacting PyPI because the clean `verify-pypi` runner had not checked out the repository and therefore could not open `scripts/verify_pypi_release.py`. Independent manifest and clean-install verification then completed successfully, and the GitHub Release was created from the exact workflow artifacts. The workflow contract is patched in the accompanying post-release recovery PR so future releases check out the exact tag before executing repository-owned verification scripts.

## Evidence quality bar

Each entry should include only the essentials external users care about:

1. Exact released package version.
2. Exact install command.
3. Environment details that were actually captured.
4. One post-install command proving usability (`python -m sdetkit --help`).
5. Distribution hashes, public references, and a plain failure/support path.

If installation fails, open a bug using the issue tracker and include the OS, Python and pip versions, full install output, and command history.
