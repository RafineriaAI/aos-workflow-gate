# GitHub Marketplace Listing (draft)

**Status: publication blocked.** Do not submit this listing while the
[Hybrid Value Gate](../benchmarks/value/ASSESSMENT.md) is `NO_GO`.
The copy below is retained as a draft, not as an active launch surface.


Publishing an Action to the Marketplace is UI-only: draft a new release,
tick **"Publish this Action to the GitHub Marketplace"**, and paste the
fields below. The listing itself is free; `action.yml` already carries the
validated name and branding.

## Fields

- **Primary category:** Continuous integration
- **Secondary category:** Security
- **Short description** (≤125 chars):

```text
Advisory self-test for your pipeline: deterministic PASS/WARN/BLOCK decision records - replayable and tamper-evident.
```

## Listing body

```markdown
CI dashboards tell you which checks passed. AOS Workflow Gate answers a
stricter question: why did the gate decide PASS, WARN, or BLOCK for this
exact commit, policy, and set of signals - as a replayable, tamper-evident
decision record.

**Zero-config Self-Test** - no checkout or policy file. The Action reads
active GitHub requirements plus exact-commit checks, suites, workflow runs,
and commit statuses. It writes one advisory decision, one next action, and
the bundle, generated policy, record, and static evidence view.

**Enforce on your terms** - keep `mode: "advisory"` while measuring noise.
Use `mode: "enforce"` only after the named gaps and remediation match the
repository's intended rules. Explicit `required-checks` fully replaces
autodiscovery; polling waits only for required controls.

**Evidence you can verify later** - canonical records detect mutation,
replay offline without a service dependency, and disclose the verifier
artifact. Export an unsigned in-toto Statement and sign it with your own
keys.

**Nothing to trust blindly** - read-only permissions (contents, checks,
actions, pull requests, statuses), no telemetry, zero runtime dependencies,
Apache-2.0. Verification steps: docs/TRUST.md. Records carry
UNSIGNED_NOT_OFFICIAL status; no production, compliance, signing, or
security-audit claim is made.
```

## After publishing

Only after the Value Gate reaches `GO`, set the repository homepage to
the Marketplace listing URL and update this file's status line below.

Status: NOT LISTED; PUBLICATION BLOCKED BY VALUE GATE.
