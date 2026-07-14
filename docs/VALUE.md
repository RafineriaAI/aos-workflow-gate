# Value

What the gate is worth to a team, stated only as far as the evidence
reaches.

**Current evidence boundary:** these are product hypotheses, not validated
market outcomes. The
[Hybrid Value Gate](../benchmarks/value/ASSESSMENT.md) is `NO_GO`. Signal
validity is inconclusive; internal product-test readiness passes; external
usability and field utility remain untested.

## Pain hypotheses

- "Why did this merge?" answered by archaeology across scattered CI logs.
- Advisory checks that look protective but can never actually block.
- A growing share of changes written by AI agents, with no tamper-evident
  trail binding a merge decision to its commit, policy, and inputs.

## Implemented mechanisms

| Hypothesis | Mechanism | Verify it yourself |
| --- | --- | --- |
| One answer instead of archaeology | A single decision record per gate run: subject, policy digest, input digests, explained reasons | `summarize` any record |
| Decisions that survive audit | Records are deterministic, tamper-evident, and replayable offline with no service dependency | `verify --input --bundle` |
| A gate that can actually block | `required-checks` + `enforce` turn advisory green-noise into an explicit contract | Failure taxonomy in [USER_FAQ.md](USER_FAQ.md) |
| Low-configuration technical path | Self-Test Mode: no config, no checkout, read-only scopes, no telemetry, zero runtime dependencies, Apache-2.0; external usability remains unvalidated | [TRUST.md](TRUST.md) |
| Standards-track evidence | in-toto Statement export, signed with your own keys | [DECISION_PREDICATE.md](DECISION_PREDICATE.md) |

## Measured, not promised

The full measured set, with method and the friction proxy, lives in
[VALUE_METRICS.md](VALUE_METRICS.md).

The replay benchmark measures implementation mechanics. The separate
[Value Gate](../benchmarks/value/README.md) measures whether evidence is
sufficient to make product-value or publication claims.

From the committed real-repository case study
([60-second version](case-studies/aos-kernel-release-surface-replay.md)):
~360 ms to first verdict (cold start), 5 real signals gated with a policy
mirroring the repository's actual branch protection, offline replay `OK`
from the committed files alone.

## What this does not promise

No security-audit, compliance, signing, SLSA, or provenance claim; `PASS`
means your explicit policy was satisfied — nothing more. Records remain
`UNSIGNED_NOT_OFFICIAL`. The full boundary lives in [SCOPE.md](SCOPE.md).
