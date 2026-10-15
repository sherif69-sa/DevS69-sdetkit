# Security Policy

Thank you for helping keep SDETKit and the people who use it safe. This document explains which versions receive security fixes, how to report a vulnerability privately, and what to expect after you do.

## Supported versions

| Version | Supported |
| --- | --- |
| 1.2.x (latest release on PyPI) | ✅ Security fixes |
| `main` (2.0.0 release candidate) | ✅ Fixed before release |
| < 1.2 | ❌ Please upgrade |

Security fixes ship in a new patch release of the latest version. If you report an issue against an older version, we may ask you to confirm it on the latest release.

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues, discussions or pull requests.**

Report them privately through GitHub's private vulnerability reporting:

1. Open the [**Report a vulnerability**](https://github.com/sherif69-sa/DevS69-sdetkit/security/advisories/new) form (Security tab → Advisories → Report a vulnerability).
2. Describe the issue using the checklist below.
3. Submit. Only the maintainers can see the report.

If you cannot use that form, open a public issue that says only that you have a security report and need a private channel, without any details, and a maintainer will contact you.

### What to include

- The affected version (`python -m pip show sdetkit`) and how it was installed.
- Your Python version and operating system.
- The command you ran and the repository or input it ran against.
- What happened, and what an attacker could achieve with it.
- Minimal steps to reproduce, with any proof of concept sanitised of real secrets.
- A suggested fix or mitigation, if you have one.

## What to expect

These are best-effort targets for a volunteer-maintained project:

| Stage | Target |
| --- | --- |
| Acknowledgement of your report | within 3 business days |
| Initial assessment and severity | within 7 business days |
| Status updates | at least every 7 business days until resolved |
| Fix for a confirmed vulnerability | in the next patch release, as soon as practical |

We will keep you informed throughout, may ask for more detail to confirm the impact, and will tell you when we disagree with a report and why.

## Coordinated disclosure

- We validate the report, prepare a fix, and publish it in a release together with a GitHub Security Advisory (and a CVE where appropriate).
- Please keep the details private until the fix is released and users have had reasonable time to upgrade. We will agree a disclosure date with you.
- We credit reporters in the advisory and the changelog unless you ask to remain anonymous.

## Security model

Knowing what SDETKit does and does not do helps you judge whether something is a vulnerability.

- **SDETKit runs your repository's code.** `gate fast` runs the repository's own tests, linters and type checker, and the test suites the repository declares. Running it on a repository is like running `pytest` there: only do it on code you trust, and use an isolated environment (for example a container or a disposable CI runner) for code you do not.
- **The release decision path makes no network requests of its own.** `gate fast`, `gate release`, `doctor` and `diagnose run` work offline; the security scan and SBOM read the repository's lockfiles locally. The project's own tests may still use the network. Commands built for HTTP work, such as `apiget`, make the requests you ask for, with redaction, timeouts and TLS verification on by default.
- **Review-first.** No command applies patches, merges, or dismisses findings on its own; every authority flag in SDETKit's output is `false`. `diagnose run --prove` tests candidate fixes in a throwaway copy of the repository.
- **Artifacts stay local.** Results are written under the paths you choose (by default `build/` and `.sdetkit/`) and are not uploaded anywhere.

In scope: anything that breaks these guarantees, for example code execution from a crafted report or log file passed to `diagnose run --log`, path traversal outside the output directory, secrets leaking into artifacts, or a command changing the repository without being asked to.

Out of scope: code execution that comes from running a repository's own tests or tools (that is how the gate works), vulnerabilities in third-party dependencies with no SDETKit-specific impact (report those upstream), and findings that need an already-compromised machine.

For hardening options and secure defaults, see [docs/security.md](docs/security.md).
