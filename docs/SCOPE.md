# Scope

`aos-workflow-gate` is the workflow decision layer around `aos-kernel`.

It is intended to collect CI, pull request, scanner, and AI-agent signals, normalize them into explicit evidence, evaluate them against a policy, and emit a replayable `PASS`, `WARN`, or `BLOCK` decision.

## In scope

- Local CLI evaluation from fixture or exported workflow signal bundles.
- GitHub pull request and release candidate gate scenarios.
- Evidence records that preserve input digests, policy identity, subject identity, and decision output.
- Advisory mode before blocking mode.
- Clear `PASS`, `WARN`, and `BLOCK` semantics aligned with the kernel verdict model.
- Minimal adapters for common public signals such as CI status, PR metadata, SARIF summaries, OpenSSF Scorecard summaries, dependency update signals, and AI-agent review summaries.

## Out of scope for early releases

- Compliance certification.
- Security-audit certification.
- Runtime proof of GitHub, CI, scanner, or AI-agent correctness.
- Signing, attestation, SBOM, SLSA, or in-toto claims unless those layers are explicitly implemented and documented later.
- Workflow orchestration dashboards.
- Automatic remediation or code generation.
- Claims that a `PASS` result means the repository is secure, correct, production-ready, or legally compliant.

## Decision boundary

A gate decision means only this:

> For the stated subject, stated policy, stated input bundle, and stated implementation version, the gate produced this verdict and evidence record.

It does not mean the underlying source signals are complete, honest, or independently verified unless a later release adds that verification layer.

## Verification status

Early outputs must use `UNSIGNED_NOT_OFFICIAL` until signing and publication controls exist. This status is a claim boundary, not a defect.
