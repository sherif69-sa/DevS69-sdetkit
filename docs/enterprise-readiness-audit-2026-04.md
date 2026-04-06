# Upgrade audit

Source pyproject: `pyproject.toml`
Requirement manifests: `requirements-docs.txt`, `requirements-test.txt`, `requirements.txt`

- packages audited: 22
- manifest drift packages: 0
- compatible multi-manifest packages: 0
- floor-and-lock baseline packages: 6
- policy-covered latest releases: 22
- policy-blocked latest releases: 0
- critical upgrade signals: 0
- high-priority upgrade signals: 0
- medium-priority upgrade signals: 0
- investigate signals: 0
- packages using cached metadata: 22
- stale cached metadata packages: 0
- latest releases compatible with repo Python policy: 22
- fallback compatible targets below latest: 0
- latest releases requiring newer Python: 0
- actionable upgrade candidates: 0
- hot-path repo-used packages: 2
- active repo-used packages: 1
- edge repo-used packages: 1
- declared-only packages: 18
- runtime core packages: 1
- quality tooling packages: 8
- integration adapter packages: 2
- fresh releases (<=14d): 8
- current releases (15-90d): 5
- aging releases (91-365d): 7
- stale releases (>365d): 2
- unknown release age packages: 0

| Package | Impact | Repo usage | Current | Target | Latest PyPI | Py policy | Source | Gap | Alignment | Policy | Signal | Risk | Action | Suggested | Release age (days) | Requirements |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `httpx` | runtime-core | hot-path (40) | `0.28.1` | `0.28.1` | `0.28.1` | compatible-latest | cache | up-to-date | floor-lock | allowed | watch | 30 | none | - | 486 | `httpx==0.28.1` <br> `httpx>=0.28.1,<1` |
| `python-telegram-bot` | integration-adapters | declared-only (0) | `22.7` | `22.7` | `22.7` | compatible-latest | cache | up-to-date | range-or-unpinned | allowed | watch | 25 | none | - | 21 | `python-telegram-bot>=22.7,<23` |
| `twilio` | integration-adapters | declared-only (0) | `9.10.4` | `9.10.4` | `9.10.4` | compatible-latest | cache | up-to-date | range-or-unpinned | allowed | watch | 25 | none | - | 13 | `twilio>=9.10.4,<10` |
| `pytest` | quality-tooling | hot-path (73) | `9.0.2` | `9.0.2` | `9.0.2` | compatible-latest | cache | up-to-date | floor-lock | allowed | watch | 20 | none | - | 120 | `pytest` <br> `pytest==9.0.2` |
| `hypothesis` | quality-tooling | edge (1) | `6.151.11` | `6.151.11` | `6.151.11` | compatible-latest | cache | up-to-date | floor-lock | allowed | watch | 18 | none | - | 1 | `hypothesis` <br> `hypothesis==6.151.11` |
| `tomli` | repo-tooling | active (2) | `2.4.1` | `2.4.1` | `2.4.1` | compatible-latest | cache | up-to-date | aligned | allowed | watch | 18 | none | - | 12 | `tomli==2.4.1; python_version < "3.11"` |
| `pytest-cov` | quality-tooling | declared-only (0) | `7.1.0` | `7.1.0` | `7.1.0` | compatible-latest | cache | up-to-date | floor-lock | allowed | watch | 15 | none | - | 16 | `pytest-cov` <br> `pytest-cov==7.1.0` |
| `build` | packaging-release | declared-only (0) | `1.4.2` | `1.4.2` | `1.4.2` | compatible-latest | cache | up-to-date | aligned | allowed | watch | 10 | none | - | 12 | `build==1.4.2` |
| `cyclonedx-bom` | security-compliance | declared-only (0) | `7.3.0` | `7.3.0` | `7.3.0` | compatible-latest | cache | up-to-date | aligned | allowed | watch | 10 | none | - | 7 | `cyclonedx-bom==7.3.0` |
| `filelock` | repo-tooling | declared-only (0) | `3.25.2` | `3.25.2` | `3.25.2` | compatible-latest | cache | up-to-date | aligned | allowed | watch | 10 | none | - | 25 | `filelock==3.25.2` |
| `mkdocs-material` | docs-tooling | declared-only (0) | `9.7.6` | `9.7.6` | `9.7.6` | compatible-latest | cache | up-to-date | aligned | allowed | watch | 10 | none | - | 18 | `mkdocs-material==9.7.6` |
| `mypy` | quality-tooling | declared-only (0) | `1.20.0` | `1.20.0` | `1.20.0` | compatible-latest | cache | up-to-date | aligned | allowed | watch | 10 | none | - | 6 | `mypy==1.20.0` |
| `pygments` | repo-tooling | declared-only (0) | `2.20.0` | `2.20.0` | `2.20.0` | compatible-latest | cache | up-to-date | aligned | allowed | watch | 10 | none | - | 8 | `pygments==2.20.0` |
| `ruff` | quality-tooling | declared-only (0) | `0.15.9` | `0.15.9` | `0.15.9` | compatible-latest | cache | up-to-date | aligned | allowed | watch | 10 | none | - | 4 | `ruff==0.15.9` |
| `pytest-asyncio` | quality-tooling | declared-only (0) | `1.3.0` | `1.3.0` | `1.3.0` | compatible-latest | cache | up-to-date | floor-lock | allowed | watch | 5 | none | - | 147 | `pytest-asyncio` <br> `pytest-asyncio==1.3.0` |
| `pytest-xdist` | repo-tooling | declared-only (0) | `3.8.0` | `3.8.0` | `3.8.0` | compatible-latest | cache | up-to-date | floor-lock | allowed | watch | 5 | none | - | 279 | `pytest-xdist[psutil]` <br> `pytest-xdist[psutil]==3.8.0` |
| `check-wheel-contents` | packaging-release | declared-only (0) | `0.6.3` | `0.6.3` | `0.6.3` | compatible-latest | cache | up-to-date | aligned | allowed | watch | 0 | none | - | 247 | `check-wheel-contents==0.6.3` |
| `mkdocs` | docs-tooling | declared-only (0) | `1.6.1` | `1.6.1` | `1.6.1` | compatible-latest | cache | up-to-date | aligned | allowed | watch | 0 | none | - | 584 | `mkdocs==1.6.1` |
| `mutmut` | quality-tooling | declared-only (0) | `3.5.0` | `3.5.0` | `3.5.0` | compatible-latest | cache | up-to-date | aligned | allowed | watch | 0 | none | - | 43 | `mutmut==3.5.0` |
| `pip-audit` | security-compliance | declared-only (0) | `2.10.0` | `2.10.0` | `2.10.0` | compatible-latest | cache | up-to-date | aligned | allowed | watch | 0 | none | - | 125 | `pip-audit==2.10.0` |
| `pre-commit` | quality-tooling | declared-only (0) | `4.5.1` | `4.5.1` | `4.5.1` | compatible-latest | cache | up-to-date | aligned | allowed | watch | 0 | none | - | 110 | `pre-commit==4.5.1` |
| `twine` | packaging-release | declared-only (0) | `6.2.0` | `6.2.0` | `6.2.0` | compatible-latest | cache | up-to-date | aligned | allowed | watch | 0 | none | - | 214 | `twine==6.2.0` |

## Priority queue

- `httpx` [watch, risk 30, lane policy-covered-watchlist, action none] -> Keep the package on watch; the declared version policy already covers the latest release.
- `python-telegram-bot` [watch, risk 25, lane policy-covered-watchlist, action none] -> Keep the package on watch; the declared version policy already covers the latest release.
- `twilio` [watch, risk 25, lane policy-covered-watchlist, action none] -> Keep the package on watch; the declared version policy already covers the latest release.
- `pytest` [watch, risk 20, lane policy-covered-watchlist, action none] -> Keep the package on watch; the declared version policy already covers the latest release.
- `hypothesis` [watch, risk 18, lane policy-covered-watchlist, action none] -> Keep the package on watch; the declared version policy already covers the latest release.

## Recommended upgrade lanes

- **policy-covered-watchlist**: 22 package(s), max risk 30 - `httpx`, `python-telegram-bot`, `twilio`, `pytest`, `hypothesis`

## Risk bands

- **low**: 16 package(s), actionable 0, max risk 30 - `httpx`, `python-telegram-bot`, `twilio`, `pytest`, `hypothesis`
- **none**: 6 package(s), actionable 0, max risk 0 - `check-wheel-contents`, `mkdocs`, `mutmut`, `pip-audit`, `pre-commit`

## Repo usage tiers

- **hot-path**: 2 package(s), actionable 0, max repo usage 73 - `httpx`, `pytest`
- **active**: 1 package(s), actionable 0, max repo usage 2 - `tomli`
- **edge**: 1 package(s), actionable 0, max repo usage 1 - `hypothesis`
- **declared-only**: 18 package(s), actionable 0, max repo usage 0 - `python-telegram-bot`, `twilio`, `pytest-cov`, `build`, `cyclonedx-bom`

## Repo hotspots

- **tests/test_apiclient.py**: 2 package(s), actionable 0, max risk 30 - `httpx`, `pytest` - lanes `policy-covered-watchlist` - validate with `bash ci.sh quick --skip-docs --artifact-dir build`, `bash quality.sh cov`, `bash quality.sh ci`
- **tests/test_apiclient_advanced.py**: 2 package(s), actionable 0, max risk 30 - `httpx`, `pytest` - lanes `policy-covered-watchlist` - validate with `bash ci.sh quick --skip-docs --artifact-dir build`, `bash quality.sh cov`, `bash quality.sh ci`
- **tests/test_apiclient_async.py**: 2 package(s), actionable 0, max risk 30 - `httpx`, `pytest` - lanes `policy-covered-watchlist` - validate with `bash ci.sh quick --skip-docs --artifact-dir build`, `bash quality.sh cov`, `bash quality.sh ci`
- **tests/test_apiclient_async_advanced.py**: 2 package(s), actionable 0, max risk 30 - `httpx`, `pytest` - lanes `policy-covered-watchlist` - validate with `bash ci.sh quick --skip-docs --artifact-dir build`, `bash quality.sh cov`, `bash quality.sh ci`
- **tests/test_apiclient_async_list.py**: 2 package(s), actionable 0, max risk 30 - `httpx`, `pytest` - lanes `policy-covered-watchlist` - validate with `bash ci.sh quick --skip-docs --artifact-dir build`, `bash quality.sh cov`, `bash quality.sh ci`

## Repo impact map

- **runtime-core**: 1 package(s), actionable 0, max risk 30 - `httpx` - validate with `bash ci.sh quick --skip-docs --artifact-dir build`, `bash quality.sh cov`
- **integration-adapters**: 2 package(s), actionable 0, max risk 25 - `python-telegram-bot`, `twilio` - validate with `bash ci.sh quick --skip-docs --artifact-dir build`, `python -m pytest -q tests/test_notify_plugins.py tests/test_notify_plugins_extra.py`
- **quality-tooling**: 8 package(s), actionable 0, max risk 20 - `pytest`, `hypothesis`, `pytest-cov`, `mypy`, `ruff` - validate with `bash quality.sh ci`, `bash quality.sh cov`
- **repo-tooling**: 4 package(s), actionable 0, max risk 18 - `tomli`, `filelock`, `pygments`, `pytest-xdist` - validate with `bash ci.sh quick --skip-docs --artifact-dir build`, `bash quality.sh ci`
- **docs-tooling**: 2 package(s), actionable 0, max risk 10 - `mkdocs-material`, `mkdocs` - validate with `bash ci.sh all --artifact-dir build`, `make docs-build`
- **packaging-release**: 3 package(s), actionable 0, max risk 10 - `build`, `check-wheel-contents`, `twine` - validate with `make package-validate`, `make release-preflight`
- **security-compliance**: 2 package(s), actionable 0, max risk 10 - `cyclonedx-bom`, `pip-audit` - validate with `bash security.sh`, `python -m sdetkit security enforce --format json`

## Release freshness

- **fresh-release**: 8 package(s), actionable 0, max risk 25 - `twilio`, `hypothesis`, `tomli`, `build`, `cyclonedx-bom`
- **aging**: 7 package(s), actionable 0, max risk 20 - `pytest`, `pytest-asyncio`, `pytest-xdist`, `check-wheel-contents`, `pip-audit`
- **current**: 5 package(s), actionable 0, max risk 25 - `python-telegram-bot`, `pytest-cov`, `filelock`, `mkdocs-material`, `mutmut`
- **stale**: 2 package(s), actionable 0, max risk 30 - `httpx`, `mkdocs`

## Manifest actions

- **none**: 22 package(s), actionable 0, max risk 30 - `httpx`, `python-telegram-bot`, `twilio`, `pytest`, `hypothesis`

## Validation commands

- `bash quality.sh cov`: 9 package(s), actionable 0, max risk 30 - `httpx`, `pytest`, `hypothesis`, `pytest-cov`, `mypy`
- `bash ci.sh quick --skip-docs --artifact-dir build`: 7 package(s), actionable 0, max risk 30 - `httpx`, `python-telegram-bot`, `twilio`, `tomli`, `filelock`
- `python -m pytest -q tests/test_notify_plugins.py tests/test_notify_plugins_extra.py`: 2 package(s), actionable 0, max risk 25 - `python-telegram-bot`, `twilio`
- `bash quality.sh ci`: 12 package(s), actionable 0, max risk 20 - `pytest`, `hypothesis`, `tomli`, `pytest-cov`, `filelock`
- `make package-validate`: 3 package(s), actionable 0, max risk 10 - `build`, `check-wheel-contents`, `twine`
- `make release-preflight`: 3 package(s), actionable 0, max risk 10 - `build`, `check-wheel-contents`, `twine`
- `bash ci.sh all --artifact-dir build`: 2 package(s), actionable 0, max risk 10 - `mkdocs-material`, `mkdocs`
- `bash security.sh`: 2 package(s), actionable 0, max risk 10 - `cyclonedx-bom`, `pip-audit`
- `make docs-build`: 2 package(s), actionable 0, max risk 10 - `mkdocs-material`, `mkdocs`
- `python -m sdetkit security enforce --format json`: 2 package(s), actionable 0, max risk 10 - `cyclonedx-bom`, `pip-audit`

## Dependency groups

- **requirements**: 19 package(s), actionable 0, max risk 30 - `httpx`, `pytest`, `hypothesis`, `tomli`, `pytest-cov`
- **default**: 1 package(s), actionable 0, max risk 30 - `httpx`
- **telegram**: 1 package(s), actionable 0, max risk 25 - `python-telegram-bot`
- **whatsapp**: 1 package(s), actionable 0, max risk 25 - `twilio`
- **test**: 5 package(s), actionable 0, max risk 20 - `pytest`, `hypothesis`, `pytest-cov`, `pytest-asyncio`, `pytest-xdist`
- **dev**: 5 package(s), actionable 0, max risk 10 - `build`, `mypy`, `ruff`, `pre-commit`, `twine`
- **packaging**: 3 package(s), actionable 0, max risk 10 - `build`, `check-wheel-contents`, `twine`
- **docs**: 2 package(s), actionable 0, max risk 10 - `mkdocs-material`, `mkdocs`

## Manifest sources

- **requirements.txt**: 18 package(s), actionable 0, max risk 30 - `httpx`, `pytest`, `hypothesis`, `tomli`, `pytest-cov`
- **pyproject.toml**: 16 package(s), actionable 0, max risk 30 - `httpx`, `python-telegram-bot`, `twilio`, `pytest`, `hypothesis`
- **requirements-test.txt**: 10 package(s), actionable 0, max risk 30 - `httpx`, `pytest`, `hypothesis`, `pytest-cov`, `mypy`
- **requirements-docs.txt**: 3 package(s), actionable 0, max risk 10 - `mkdocs-material`, `pygments`, `mkdocs`

## Focus notes

- `httpx` [runtime-core] (Keep the package on watch; the declared version policy already covers the latest release.) Cross-manifest requirements follow a floor-and-lock pattern with a tested pinned baseline. Latest PyPI release is already allowed by the declared version policy. Repo Python support policy: >=3.11. Repo impact area: runtime-core. Repo usage: 40 file(s), tier hot-path; observed in src/sdetkit/__main__.py, src/sdetkit/apiclient.py, src/sdetkit/apiget.py (+37 more). Latest metadata source: cache. Validate with `bash ci.sh quick --skip-docs --artifact-dir build`, `bash quality.sh cov`.
- `python-telegram-bot` [integration-adapters] (Keep the package on watch; the declared version policy already covers the latest release.) Package is not pinned to a single exact version. Latest PyPI release is already allowed by the declared version policy. Latest PyPI release is recent enough to merit fast follow-up validation. Repo Python support policy: >=3.11. Repo impact area: integration-adapters. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `bash ci.sh quick --skip-docs --artifact-dir build`, `python -m pytest -q tests/test_notify_plugins.py tests/test_notify_plugins_extra.py`.
- `twilio` [integration-adapters] (Keep the package on watch; the declared version policy already covers the latest release.) Package is not pinned to a single exact version. Latest PyPI release is already allowed by the declared version policy. Latest PyPI release is recent enough to merit fast follow-up validation. Repo Python support policy: >=3.11. Repo impact area: integration-adapters. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `bash ci.sh quick --skip-docs --artifact-dir build`, `python -m pytest -q tests/test_notify_plugins.py tests/test_notify_plugins_extra.py`.
- `pytest` [quality-tooling] (Keep the package on watch; the declared version policy already covers the latest release.) Cross-manifest requirements follow a floor-and-lock pattern with a tested pinned baseline. Latest PyPI release is already allowed by the declared version policy. Repo Python support policy: >=3.11. Repo impact area: quality-tooling. Repo usage: 73 file(s), tier hot-path; observed in tests/test_agent_actions_extra.py, tests/test_agent_omnichannel_extra.py, tests/test_agent_providers_extra.py (+70 more). Latest metadata source: cache. Validate with `bash quality.sh ci`, `bash quality.sh cov`.
- `hypothesis` [quality-tooling] (Keep the package on watch; the declared version policy already covers the latest release.) Cross-manifest requirements follow a floor-and-lock pattern with a tested pinned baseline. Latest PyPI release is already allowed by the declared version policy. Latest PyPI release is recent enough to merit fast follow-up validation. Repo Python support policy: >=3.11. Repo impact area: quality-tooling. Repo usage: 1 file(s), tier edge; observed in tests/test_textutil.py. Latest metadata source: cache. Validate with `bash quality.sh ci`, `bash quality.sh cov`.
- `tomli` [repo-tooling] (Keep the package on watch; the declared version policy already covers the latest release.) Latest PyPI release is already allowed by the declared version policy. Latest PyPI release is recent enough to merit fast follow-up validation. Repo Python support policy: >=3.11. Repo impact area: repo-tooling. Repo usage: 2 file(s), tier active; observed in src/sdetkit/projects.py, tests/test_entrypoints_cassette_get.py. Latest metadata source: cache. Validate with `bash ci.sh quick --skip-docs --artifact-dir build`, `bash quality.sh ci`.
- `pytest-cov` [quality-tooling] (Keep the package on watch; the declared version policy already covers the latest release.) Cross-manifest requirements follow a floor-and-lock pattern with a tested pinned baseline. Latest PyPI release is already allowed by the declared version policy. Latest PyPI release is recent enough to merit fast follow-up validation. Repo Python support policy: >=3.11. Repo impact area: quality-tooling. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `bash quality.sh ci`, `bash quality.sh cov`.
- `build` [packaging-release] (Keep the package on watch; the declared version policy already covers the latest release.) Latest PyPI release is already allowed by the declared version policy. Latest PyPI release is recent enough to merit fast follow-up validation. Repo Python support policy: >=3.11. Repo impact area: packaging-release. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `make package-validate`, `make release-preflight`.
- `cyclonedx-bom` [security-compliance] (Keep the package on watch; the declared version policy already covers the latest release.) Latest PyPI release is already allowed by the declared version policy. Latest PyPI release is recent enough to merit fast follow-up validation. Repo Python support policy: >=3.11. Repo impact area: security-compliance. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `bash security.sh`, `python -m sdetkit security enforce --format json`.
- `filelock` [repo-tooling] (Keep the package on watch; the declared version policy already covers the latest release.) Latest PyPI release is already allowed by the declared version policy. Latest PyPI release is recent enough to merit fast follow-up validation. Repo Python support policy: >=3.11. Repo impact area: repo-tooling. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `bash ci.sh quick --skip-docs --artifact-dir build`, `bash quality.sh ci`.
- `mkdocs-material` [docs-tooling] (Keep the package on watch; the declared version policy already covers the latest release.) Latest PyPI release is already allowed by the declared version policy. Latest PyPI release is recent enough to merit fast follow-up validation. Repo Python support policy: >=3.11. Repo impact area: docs-tooling. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `bash ci.sh all --artifact-dir build`, `make docs-build`.
- `mypy` [quality-tooling] (Keep the package on watch; the declared version policy already covers the latest release.) Latest PyPI release is already allowed by the declared version policy. Latest PyPI release is recent enough to merit fast follow-up validation. Repo Python support policy: >=3.11. Repo impact area: quality-tooling. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `bash quality.sh ci`, `bash quality.sh cov`.
- `pygments` [repo-tooling] (Keep the package on watch; the declared version policy already covers the latest release.) Latest PyPI release is already allowed by the declared version policy. Latest PyPI release is recent enough to merit fast follow-up validation. Repo Python support policy: >=3.11. Repo impact area: repo-tooling. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `bash ci.sh quick --skip-docs --artifact-dir build`, `bash quality.sh ci`.
- `ruff` [quality-tooling] (Keep the package on watch; the declared version policy already covers the latest release.) Latest PyPI release is already allowed by the declared version policy. Latest PyPI release is recent enough to merit fast follow-up validation. Repo Python support policy: >=3.11. Repo impact area: quality-tooling. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `bash quality.sh ci`, `bash quality.sh cov`.
- `pytest-asyncio` [quality-tooling] (Keep the package on watch; the declared version policy already covers the latest release.) Cross-manifest requirements follow a floor-and-lock pattern with a tested pinned baseline. Latest PyPI release is already allowed by the declared version policy. Repo Python support policy: >=3.11. Repo impact area: quality-tooling. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `bash quality.sh ci`, `bash quality.sh cov`.
- `pytest-xdist` [repo-tooling] (Keep the package on watch; the declared version policy already covers the latest release.) Cross-manifest requirements follow a floor-and-lock pattern with a tested pinned baseline. Latest PyPI release is already allowed by the declared version policy. Repo Python support policy: >=3.11. Repo impact area: repo-tooling. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `bash ci.sh quick --skip-docs --artifact-dir build`, `bash quality.sh ci`.
- `check-wheel-contents` [packaging-release] (Keep the package on watch; the declared version policy already covers the latest release.) Latest PyPI release is already allowed by the declared version policy. Repo Python support policy: >=3.11. Repo impact area: packaging-release. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `make package-validate`, `make release-preflight`.
- `mkdocs` [docs-tooling] (Keep the package on watch; the declared version policy already covers the latest release.) Latest PyPI release is already allowed by the declared version policy. Repo Python support policy: >=3.11. Repo impact area: docs-tooling. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `bash ci.sh all --artifact-dir build`, `make docs-build`.
- `mutmut` [quality-tooling] (Keep the package on watch; the declared version policy already covers the latest release.) Latest PyPI release is already allowed by the declared version policy. Repo Python support policy: >=3.11. Repo impact area: quality-tooling. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `bash quality.sh ci`, `bash quality.sh cov`.
- `pip-audit` [security-compliance] (Keep the package on watch; the declared version policy already covers the latest release.) Latest PyPI release is already allowed by the declared version policy. Repo Python support policy: >=3.11. Repo impact area: security-compliance. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `bash security.sh`, `python -m sdetkit security enforce --format json`.
- `pre-commit` [quality-tooling] (Keep the package on watch; the declared version policy already covers the latest release.) Latest PyPI release is already allowed by the declared version policy. Repo Python support policy: >=3.11. Repo impact area: quality-tooling. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `bash quality.sh ci`, `bash quality.sh cov`.
- `twine` [packaging-release] (Keep the package on watch; the declared version policy already covers the latest release.) Latest PyPI release is already allowed by the declared version policy. Repo Python support policy: >=3.11. Repo impact area: packaging-release. Repo usage: declared in manifests but not imported from tracked src/tests Python files. Latest metadata source: cache. Validate with `make package-validate`, `make release-preflight`.
