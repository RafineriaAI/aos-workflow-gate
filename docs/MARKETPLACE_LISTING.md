# GitHub Marketplace Listing (draft)

**Status: publication blocked.** Do not submit this listing while the
[Incremental Value Gate](../benchmarks/value/ASSESSMENT.md) is `NO_GO`.
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

**Zero-config Self-Test** - add one step, no checkout, no configuration:
the action collects your commit's completed check runs, generates an
explicit advisory policy, and writes a decision record plus a job summary
that answers: what happened, can this gate block, what to fix next.

**Enforce on your terms** - name your required-checks (missing or failed
means BLOCK) and set enforce: "true" when you want a BLOCK verdict to
fail the job. Poll slow checks with wait-for-checks.

**Evidence that survives audit** - records are deterministic, replay
offline with no service dependency, and refuse tampering. Export as an
unsigned in-toto
Statement and sign with your own keys.

**Nothing to trust blindly** - read-only permissions (contents + checks),
no telemetry, zero runtime dependencies, Apache-2.0. Verification steps
for every claim: docs/TRUST.md. Records carry UNSIGNED_NOT_OFFICIAL
status; no production, compliance, or security-audit claim is made.
```

## After publishing

Only after the Value Gate reaches `GO`, set the repository homepage to
the Marketplace listing URL and update this file's status line below.

Status: NOT LISTED; PUBLICATION BLOCKED BY VALUE GATE.
