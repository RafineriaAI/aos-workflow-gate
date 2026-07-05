# AOS Workflow Gate — One-Pager

**RafineriaAI builds deterministic evidence infrastructure for
AI-controlled workflows — starting with replayable CI and release-gate
decisions.**

## The problem

Platform, release, and security teams adopting AI coding agents cannot
answer *"why did this merge?"* without archaeology across CI logs.
Advisory checks look protective but never block; nothing tamper-evident
binds a decision to its commit, policy, and inputs.

## The product

`aos-workflow-gate`: GitHub Action + CLI for replayable CI/PR/release
gate decisions. Zero-config Self-Test, deterministic `PASS`/`WARN`/`BLOCK`
records that are tamper-evident and replay offline. Read-only scopes, no
telemetry, zero runtime dependencies, Apache-2.0. GitHub.com and GHES
natively; GitLab CI and Jenkins via the platform-neutral CLI.

## How it works (60 seconds)

1. Add the action — no checkout, no config
   (`uses: RafineriaAI/aos-workflow-gate@v0.11.1`).
2. The job summary answers: what happened, can this gate block, what to
   fix next.
3. Name your `required-checks` and set `enforce: "true"` when ready —
   the gate goes from evidence to enforcement on your terms.

## Proof, not promises

Real-repository case study
([60-second version](case-studies/aos-kernel-release-surface-replay.md)):
~360 ms to verdict, real branch-protection policy, offline replay from
committed files. Every claim has a self-verification step in
[TRUST.md](TRUST.md); every failure symptom has a fix in
[USER_FAQ.md](USER_FAQ.md).

## Engagement paths

| Path | Cost | What happens |
| --- | --- | --- |
| Self-serve | Free (Apache-2.0, no feature gates) | Add the action; you own everything it produces |
| [Guided pilot](GUIDED_PILOT.md) | Paid, scoped individually | We design the policy for one real workflow, wire it in, hand over measured, replayable results |
| [Design partner](GUIDED_PILOT.md#design-partner-variant) | Reduced scope fee | Pilot terms plus roadmap influence, in exchange for structured feedback |

**Start:** [guided-pilot scoping form](https://github.com/RafineriaAI/aos-workflow-gate/issues/new?template=guided-pilot-scoping.yml)
— submitting commits neither side.

## Boundary

No security-audit, compliance, signing, SLSA, or provenance claim.
Decision records remain `UNSIGNED_NOT_OFFICIAL`; `PASS` means your
explicit policy was satisfied — nothing more.
