# Adaptive hosted/managed readiness boundary

The adaptive next wave remains local-first. This boundary defines what can safely become a managed or hosted input later and what must stay local-only until stronger privacy, tenancy, and data-retention controls exist.

## Local-only evidence

These artifacts should stay on the operator workstation or CI artifact store by default:

- raw adaptive diagnosis logs and stack traces;
- operator briefs that include repository context;
- fix-audit JSONL with notes, source paths, changed files, and proof commands;
- assisted patch plans and safe-fix plans before redaction;
- dashboard HTML that links local artifact paths.

## Optional managed inputs later

The following can be considered for managed workflows only after explicit opt-in and redaction validation:

- anonymized learning exports with `<redacted>` private fields;
- aggregate enterprise analytics metrics without raw paths;
- portfolio counts and source-code recurrence without repository identifiers;
- adapter contract status with artifact names normalized.

## Unsupported data classes

Do not send these to any hosted service from this toolkit lane:

- secrets, tokens, credentials, or environment dumps;
- raw source files or patches;
- customer data, production payloads, or screenshots containing private data;
- unredacted repository names, usernames, hostnames, absolute paths, or private issue links.

## Readiness rule

Hosted behavior remains unsupported until documentation, retention controls, tenant isolation, deletion workflow, and redaction enforcement are implemented and tested. Until then, deterministic static artifacts and anonymized imports are the supported boundary.
