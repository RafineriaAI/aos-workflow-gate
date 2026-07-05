# Security Policy

## Supported status

`aos-workflow-gate` is currently in public bootstrap. There is no production release yet.

## Reporting security issues

Please report suspected security issues privately through GitHub private
vulnerability reporting:
[Report a vulnerability](https://github.com/RafineriaAI/aos-workflow-gate/security/advisories/new)
(repository **Security** tab -> **Report a vulnerability**). Do not open a
public issue for suspected vulnerabilities.

Include:

- Affected commit or release.
- Reproduction steps.
- Expected and actual behavior.
- Whether the issue affects decision integrity, evidence handling, CI permissions, or documentation claims.

## Claim boundary

At this stage, this repository does not claim to provide a security audit, compliance certification, signed provenance, or a guaranteed production release gate.

The GitHub Action uses least-privilege, read-only permissions (`contents: read` plus `checks: read` for Self-Test Mode) and treats all external workflow inputs as untrusted.
