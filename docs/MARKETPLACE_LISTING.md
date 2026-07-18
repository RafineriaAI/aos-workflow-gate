# GitHub Marketplace Listing (draft)

**Status: publication blocked.** Do not submit this listing while the
[Hybrid Value Gate](../benchmarks/value/ASSESSMENT.md) is `NO_GO`.
The copy below is retained as a draft, not as an active launch surface.

Publishing an Action to the Marketplace is UI-only: draft a new release, tick
**"Publish this Action to the GitHub Marketplace"**, and paste the fields
below. The listing itself is free; `action.yml` carries the validated name and
branding.

## Fields

- **Primary category:** Continuous integration
- **Secondary category:** Security
- **Short description** (<=125 chars):

```text
Verify which CI/CD controls governed the exact PR commit, with one actionable verdict and replayable evidence.
```

## Listing body

```markdown
A green PR can still rely on a control that is missing, stale, produced by the
wrong app, or modified by the same PR. AOS Workflow Gate verifies the gate,
not the code.

**Exact-commit control assurance** - read active GitHub requirements plus
checks, suites, workflow runs, and statuses for the head SHA. Get one
PASS/WARN/BLOCK verdict, one reason, one next action, and replayable evidence.

**Advisory before enforcement** - observe real repository behavior and tune
policy before making BLOCK fail a job. The summary separates a GitHub-native
block from an incremental AOS policy or evidence gap.

**Evidence you can verify later** - canonical records bind subject, policy,
inputs, and verifier artifact. Replay offline without a service dependency, or
export an unsigned in-toto Statement for operator-key signing.

**Nothing to trust blindly** - read-only permissions, no code upload, no
telemetry, zero runtime dependencies, and Apache-2.0. Records carry
UNSIGNED_NOT_OFFICIAL status; no production, compliance, signing, SLSA,
security-audit, or code-quality claim is made.
```

## After publishing

Only after the Value Gate reaches `GO`, set the repository homepage to the
Marketplace listing URL and update this file's status.

Status: NOT LISTED; PUBLICATION BLOCKED BY VALUE GATE.
