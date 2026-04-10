<div align="center">

# Security Policy

Security is treated as a product feature in this repository.

[README](README.md) · [Security Docs](docs/security.md) · [Support](SUPPORT.md) · [Live Docs](https://sherif69-sa.github.io/DevS69-sdetkit/)

</div>

---

## Supported versions

- Security fixes are provided for the **latest released version**.
- If you report an issue against an older version, maintainers may ask you to retest on the latest release before triage is finalized.

## How to report vulnerabilities privately

Please **do not open public issues** for suspected vulnerabilities.

1. Use GitHub Security Advisories for this repository to submit a private report.
2. If GitHub Security Advisories is unavailable, use the private contact channel listed in [SUPPORT.md](SUPPORT.md) and request private handling.
3. Include the details listed in [What to include in your report](#what-to-include-in-your-report).

## Response targets

Our targets are best-effort and may vary with report quality and maintainer availability.

- **Initial triage response:** within **3 business days**.
- **Status updates:** at least every **7 business days** until closure or coordinated disclosure.
- **Remediation goal:** confirmed vulnerabilities are addressed in the next available patch release when practical.

## Coordinated disclosure policy

- Coordinated disclosure begins after maintainers validate the report.
- Public disclosure should wait until a fix is released and users have had reasonable time to upgrade.
- Maintainers may request additional validation details (for example, PoC steps) to confirm impact.
- Reporter credit is included in release notes unless anonymity is requested.

### What NOT to do

- Do not publish exploit details, proof-of-concept code, or sensitive reproduction data before a fix is available.
- Do not open duplicate public issues for active private security reports.

## What to include in your report

Provide enough detail for deterministic triage:

- affected version(s) and environment,
- impact and severity assessment,
- minimal reproducible steps,
- proof-of-concept or sample payloads (sanitized),
- suggested mitigations or fix direction (if known).

For additional hardening context, see [docs/security.md](docs/security.md).
