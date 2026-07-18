# AOS Workflow Gate - One-Pager

**Status: free self-serve advisory validation is open.** The mechanism is
tested; external utility and market value remain unvalidated, so the
[Hybrid Value Gate](../benchmarks/value/ASSESSMENT.md) remains `NO_GO` for
efficacy, production, paid-pilot, and ROI claims.

**Detect a control that is missing, stale, produced by the wrong app, or
modified by the same PR.**

AOS verifies the gate, not the code. It is a read-only **pre-merge control
assurance** tool for the exact PR commit, with one `PASS/WARN/BLOCK` verdict,
one reason, one next action, and replayable evidence.

## Business problem

A green PR can still be governed by a control that did not run, ran for the
wrong subject, came from the wrong integration, or was modified by the same PR.
The failure may be infrequent, but its handling cost grows when maintainers
must reconstruct branch rules, checks, workflow state, identity, and commit
binding after the fact.

The product hypothesis is therefore assurance and investigation-time
reduction, not a high volume of alerts.

## Product

For one exact commit, AOS records five bounded properties:

1. **Continuity** - did every intended control produce an observation?
2. **Identity** - did app-bound evidence come from the expected integration?
3. **Subject binding** - does the evidence belong to this repository and SHA?
4. **Independence** - did the PR modify the workflow that assessed it?
5. **Replay** - can another operator verify the same decision later?

It does not review code, detect AI authorship, replace CI, or certify security.

## Best fit

- Maintainers and platform or DevSecOps owners responsible for controls across
  multiple repositories.
- Teams with GitHub rulesets, agent-assisted change volume, or evidence and
  review obligations.
- Security and assurance reviewers who need bounded exact-commit records
  without source-code upload, write permissions, telemetry, or a hosted
  dependency.

Not the primary paid use case: an individual developer or a repository with
few controls and low-cost failures. The free CLI may still provide occasional
pre-review clarity.

## First-run flow

1. Add the Action - no checkout, policy, or required-check list
   (`uses: RafineriaAI/aos-workflow-gate@v0.37.1`).
2. AOS reads branch rules and exact-commit checks, then names the dominant
   control gap, effect, and next action.
3. Keep advisory while measuring acceptance and repeated noise. Enable
   enforcement only after repository owners confirm the policy.

## Differentiation

Existing tools produce code findings, statuses, policy results, or
attestations. AOS consumes those signals and answers a narrower question:
**did the intended controls actually govern this exact change?**

The differentiating bundle is exact-SHA binding, app-bound control identity,
verifier independence, deterministic policy, and offline replay. Each
primitive exists elsewhere; superiority of the combined product is not yet
market-validated.

## Product and commercial hypothesis

The Apache-2.0 CLI and Action remain free, local-first, and advisory by
default. There is no active paid offering.

A future B2B product is justified only if external evidence supports demand
for cross-repository control inventory and drift, exception governance,
evidence retention and export, assurance reporting, or an official signing
service. Policy packs alone are too copyable to be the primary commercial
moat.

Required evidence includes actionable-alert rate, decision-change rate,
incremental value over GitHub, alert acceptance, repeated-alert rate,
time-to-resolution, evidence-handling time saved, and 30-day retention.
Downloads and internally generated cases are not substitutes.

## Technical proof

The [exact-commit contrast](../benchmarks/value/EXACT_CONTRAST.md) and
[real-repository replay](case-studies/aos-kernel-release-surface-replay.md)
demonstrate deterministic mechanics and offline replay. These artifacts prove
a bounded semantic difference, not practical usefulness, low noise, incident
reduction, or willingness to pay.

## Boundary

No security-audit, compliance, signing, SLSA, provenance, or ROI claim.
Decision records remain `UNSIGNED_NOT_OFFICIAL`; `PASS` means the explicit
policy was satisfied - nothing more.
