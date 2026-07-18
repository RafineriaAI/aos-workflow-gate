# Security Policy

## Supported status

The latest immutable GitHub release and current `main` receive security
fixes. Older release lines are not maintained unless a notice says otherwise.

`aos-workflow-gate` is a free public advisory preview, not a production
security control or security-audit product. Supported here means that reported
vulnerabilities in the published code and evidence path will be assessed and,
when confirmed, fixed in a new immutable release. It is not a service-level,
availability, or defect-absence guarantee.

## Reporting security issues

Report suspected vulnerabilities privately through GitHub private
vulnerability reporting:

[Report a vulnerability](https://github.com/RafineriaAI/aos-workflow-gate/security/advisories/new)

Use the repository **Security** tab and **Report a vulnerability**. Do not open
a public issue for suspected vulnerabilities.

Include:

- affected commit or immutable release;
- reproduction steps and the smallest safe artifact needed to reproduce;
- expected and actual behavior;
- impact on decision integrity, canonicalization, evidence handling,
  permissions, output paths, or documentation claims;
- whether public disclosure is already known.

Do not include third-party secrets, private source code, or credentials. There
is no guaranteed response SLA; the maintainer will acknowledge and triage
reports as capacity permits.

## Data and permission boundary

The GitHub Action uses read-only permissions. Tokens remain in the process
environment and are not written into decision evidence. Zero-config collection
reads metadata for repository rules, checks, workflow runs, pull requests, and
commit statuses; it does not upload source code to RafineriaAI and has no
telemetry.

The detailed threat model, private-repository data table, input bounds,
workspace controls, and known limits are in
[docs/SECURITY_READINESS.md](docs/SECURITY_READINESS.md).

## Claim boundary

This repository does not provide a security audit, compliance certification,
signed provenance, guaranteed production release gate, or proof that source
signals are truthful. A `PASS` proves only that declared policy requirements
were satisfied by the recorded evidence. Outputs remain
`UNSIGNED_NOT_OFFICIAL`.
