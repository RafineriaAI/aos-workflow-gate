# AOS Workflow Gate — One-Pager

**Status: pre-pilot validation; external intake closed.** The current
[Hybrid Value Gate](../benchmarks/value/ASSESSMENT.md) decision is
`NO_GO`.


**RafineriaAI builds deterministic evidence infrastructure for
AI-controlled workflows — starting with replayable CI and release-gate
decisions.**

## Problem hypothesis

Some platform, release, and security teams adopting AI coding agents may
struggle to answer *"why did this merge?"* without archaeology across CI
logs. Advisory checks can look protective while remaining non-blocking, and
the merge decision may not be bound to its commit, policy, and inputs.

## The product

`aos-workflow-gate`: GitHub Action + CLI for replayable CI/PR/release
gate decisions. Zero-config Self-Test, deterministic `PASS`/`WARN`/`BLOCK`
records that are tamper-evident and replay offline. Read-only scopes, no
telemetry, zero runtime dependencies, Apache-2.0. GitHub.com and GHES
natively; GitLab CI and Jenkins via the platform-neutral CLI.

## Technical flow

1. Add the action — no checkout, no config
   (`uses: RafineriaAI/aos-workflow-gate@v0.36.0`).
2. The job summary answers: what happened, can this gate block, what to
   fix next.
3. Name your `required-checks` and set `enforce: "true"` when ready —
   the gate goes from evidence to enforcement on your terms.

## Technical proof

The [real-repository replay case](case-studies/aos-kernel-release-surface-replay.md)
demonstrates deterministic evaluation and offline replay from committed
files. [TRUST.md](TRUST.md) provides self-verification steps and
[USER_FAQ.md](USER_FAQ.md) maps operational failures to remediation. These
artifacts prove mechanics, not incremental product value, production
effectiveness, or low false-positive rates.

## Availability

The Apache-2.0 source remains available for internal, advisory technical
evaluation. External onboarding, production recommendations, paid pilots,
and design-partner intake remain closed until the Value Gate reaches
`GO`. [GUIDED_PILOT.md](GUIDED_PILOT.md) is a future specification, not
an active offer.

## Boundary

No security-audit, compliance, signing, SLSA, or provenance claim.
Decision records remain `UNSIGNED_NOT_OFFICIAL`; `PASS` means your
explicit policy was satisfied — nothing more.
