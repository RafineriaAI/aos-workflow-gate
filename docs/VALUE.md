# Value

What pre-merge control assurance may be worth to a team, stated only as far as
the evidence reaches.

**Current evidence boundary:** the mechanisms below are implemented, but the
business outcomes remain hypotheses. The
[Hybrid Value Gate](../benchmarks/value/ASSESSMENT.md) is `NO_GO`; external
usability, alert precision, retention, decision impact, and willingness to pay
remain unvalidated.

## Mass-market product hypothesis

The `0.38.0` candidate tests a broader and more frequent job:

> I built or changed a project. Check it before I share or deploy it, explain
> what actually ran, and tell me the next action without requiring Git or test
> expertise.

`aos-check` detects conventional project metadata and executes existing build
and behavioral checks. This can reduce setup and interpretation friction for
beginners and coding-agent users, but orchestration alone is not a defensible
market advantage. The candidate must not be sold as general code correctness.

Mass-product advancement requires accepted incremental findings beyond the
project's familiar commands: browser-level flow failures, adversarial tests,
change-sensitive verification, or successful agent remediation followed by
independent re-check. Required metrics are time to first result, completion,
actionable and remediation-acceptance rates, incremental finding rate,
inconclusive/noise rate, repeat use, and 30-day retention.


## Stronger code-value experiment

Control assurance is a low-frequency, potentially high-cost job. It may be too
infrequent to sustain daily developer value on its own. The experimental
`prove-change` path tests a separate, higher-frequency pain:

> Green tests can pass even when they do not distinguish the implementation
> introduced by the PR from the implementation it replaces.

AOS runs the same explicit verifier at `HEAD` and with selected implementation
changes removed. The immediate artifact is executable evidence that the checks
are change-sensitive, insensitive, failing at `HEAD`, or inconclusive. This is
more actionable than another review comment, but it remains a product
hypothesis rather than a proven market advantage.

The commercial hypothesis is reduced reviewer uncertainty and fewer weak tests
on agent-assisted PRs. It is viable only if external maintainers accept the
finding, add or strengthen tests, change merge decisions, and retain the check
at a runtime cost lower than the review or regression cost avoided. The
comparison baseline must include ordinary CI, changed-test heuristics, and
established mutation-testing tools.

## Business problem

A green PR is a collection of reported results, not proof that every intended
control governed the exact change. A control may be absent, stale, bound to the
wrong subject, emitted by the wrong integration, or changed by the same PR.
Investigating that failure requires reconstructing state spread across GitHub
rules, checks, workflows, statuses, policy, and commit history.

This is usually a **low-frequency, potentially high-cost** control-plane
failure. The value hypothesis is reduced uncertainty and investigation effort,
not frequent developer notifications.

## Product value thesis

| Operator question | AOS mechanism | Bounded outcome |
| --- | --- | --- |
| Did every intended control run? | Required-source discovery and fail-closed missing, pending, failed, or incomplete states | Named continuity gap |
| Did the expected integration produce it? | Control identity `(context, integration_id)` | Wrong or unverifiable producer is not treated as satisfied |
| Does the evidence belong to this change? | Repository, PR, branch, and exact-SHA subject binding | Cross-subject and stale reuse fail closed |
| Did a verifier assess its own modification? | Workflow-change to check-suite correlation | Deterministic `non_independent_evidence` signal |
| Can the decision be checked later? | Canonical bundle, policy digest, verifier manifest, record digest, and replay | Portable `UNSIGNED_NOT_OFFICIAL` evidence |

AOS does not improve the underlying test, scanner, or review. It verifies and
records how those controls governed one exact commit.

## Best-fit user and buyer

- **Primary operator:** maintainer, platform engineer, or DevSecOps owner.
- **Assurance consumer:** security, engineering governance, or audit-support
  reviewer.
- **Potential buyer:** the owner of consistent software-delivery controls
  across repositories.
- **Weak paid fit:** an individual developer, a single low-control repository,
  or a team whose failures are inexpensive and easy to reconstruct.

The initial ICP hypothesis is a GitHub-based organization with multiple
repositories, formal rulesets, growing agent-assisted change volume, or
repeatable evidence obligations. This hypothesis still requires external
validation.

## Implemented mechanisms

| Hypothesis | Mechanism | Verify it yourself |
| --- | --- | --- |
| One answer instead of control archaeology | A single decision record per gate run: subject, policy digest, input digests, explained reasons | `summarize` any record |
| Decisions that survive handoff | Records are deterministic, tamper-evident, and replayable offline with no service dependency | `verify --input --bundle` |
| Advisory before enforcement | Verdict and exit behavior are separate; policy owners can observe noise first | [USER_FAQ.md](USER_FAQ.md) |
| Low-friction technical path | No config, checkout, write scope, telemetry, runtime dependency, or account | [TRUST.md](TRUST.md) |
| Operator-owned export | Unsigned in-toto Statement export, signable with operator keys | [DECISION_PREDICATE.md](DECISION_PREDICATE.md) |

## Commercial packaging hypothesis

The free Apache-2.0 Action and CLI are the trust and validation surface. There
is no active paid offering.

A future paid B2B layer would need to solve organization-level jobs that are
not naturally delivered by a single repository Action:

- cross-repository control inventory and drift;
- exception, override, and owner governance;
- durable evidence retention and controlled export;
- assurance reporting and policy rollout visibility;
- optional official signing or managed verification, only after a separate
  trust and security program.

Policy packs alone are too copyable to form a durable moat;
`PASS/WARN/BLOCK` is also a feature, not a category. A defensible advantage would require a high-precision corpus of real
control-plane failures, low-noise remediation, evidence interoperability, and
trusted organization-wide operations.

## Evidence required before commercialization

The primary field metrics are:

- actionable rate and alert acceptance rate;
- decision-change rate;
- incremental finding rate over GitHub and a naive workflow-change baseline;
- repeated-alert and independently adjudicated noise rates;
- time-to-resolution and evidence-gathering time saved;
- override closure and control-drift detection rates;
- activation, 30-day retained installation, and repository expansion;
- willingness to pay from the control owner, not only positive developer
  feedback.

These metrics must be measured in external use. Downloads, stars, internal
benchmarks, and mechanism correctness do not establish product value.

## Measured, not promised

The current measured set and its method live in
[VALUE_METRICS.md](VALUE_METRICS.md). The replay benchmark measures
implementation mechanics. The separate
[Value Gate](../benchmarks/value/README.md) determines whether evidence is
sufficient for product-value claims.

The committed cases show sub-second local decisions, exact-subject records,
and offline replay. They do not establish avoided incidents, saved money,
retention, or commercial demand.

## What this does not promise

No security-audit, compliance, signing, SLSA, provenance, protection-quality,
or ROI claim. `PASS` means the explicit policy was satisfied - nothing more.
Records remain `UNSIGNED_NOT_OFFICIAL`. The full boundary lives in
[SCOPE.md](SCOPE.md).
