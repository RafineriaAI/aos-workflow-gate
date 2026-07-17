# AOS Workflow Gate - One-Pager

**Status: free self-serve advisory validation is open.** The mechanism is
tested; external utility and market value remain unvalidated, so the
[Hybrid Value Gate](../benchmarks/value/ASSESSMENT.md) remains `NO_GO` for
efficacy, production, paid-pilot, and ROI claims.

**Find merge-control gaps that a green GitHub view can miss. Get one
plain `PASS/WARN/BLOCK` decision, one reason, and one next action before
merge.**

## Problem hypothesis

GitHub can permit merge when no status check is required. A PR can also
change the workflow that produces its own green checks. Developers and
maintainers must otherwise cross-check branch rules, check runs, workflow
state, and the exact commit by hand.

## The product

`aos-workflow-gate` is a read-only GitHub Action and CLI. It compares
active requirements with checks on the exact commit, names the dominant
gap, gives one remediation, and saves the decision for offline
verification. It does not review code or detect AI authorship.

Immediate developer value: less manual pre-review checking. Team value:
consistent repository decisions. Platform and security value: bounded
exact-commit records without source-code upload, write scopes, or telemetry.

## First-run flow

1. Add the Action - no checkout, policy, or required-check list
   (`uses: RafineriaAI/aos-workflow-gate@v0.35.0`).
2. AOS reads branch rules and exact-commit checks, then answers: what is
   missing, what this verdict can do, and what to do next.
3. Keep advisory while measuring noise. Enable enforcement only after the
   repository behavior is stable and useful.

## Technical proof

The [real-repository replay case](case-studies/aos-kernel-release-surface-replay.md)
demonstrates deterministic evaluation and offline replay from committed
files. [TRUST.md](TRUST.md) provides self-verification steps and
[USER_FAQ.md](USER_FAQ.md) maps operational failures to remediation. These
artifacts prove mechanics, not incremental product value, production
effectiveness, or low false-positive rates.

## Availability

The Apache-2.0 CLI and Action are available free for public self-serve
validation in advisory mode, with no account or telemetry. Feedback is
opt-in. Production recommendations, efficacy claims, paid pilots, and
design-partner intake remain closed while the Value Gate is `NO_GO`.
[GUIDED_PILOT.md](GUIDED_PILOT.md) is not an active offer.

## Boundary

No security-audit, compliance, signing, SLSA, or provenance claim.
Decision records remain `UNSIGNED_NOT_OFFICIAL`; `PASS` means your
explicit policy was satisfied — nothing more.
