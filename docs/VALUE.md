# Value

What pre-merge control assurance may be worth to a team, stated only as far as
the evidence reaches.

**Current evidence boundary:** the mechanisms below are implemented, but the
business outcomes remain hypotheses. The
[Hybrid Value Gate](../benchmarks/value/ASSESSMENT.md) is `NO_GO`; external
usability, alert precision, retention, decision impact, and willingness to pay
remain unvalidated.

## Entry utility, not primary differentiation

`aos-check` removes command-discovery and first-run friction for conventional
projects. It is useful onboarding, but re-running familiar build and test
commands is not a strong standalone market advantage. The frozen
60-repository remeasurement improved nested project discovery in 7 cases
(11.7%); it did not measure accepted actions, decision change, retention, or
willingness to pay.

The current product direction is therefore an add-on to existing verification,
not a new all-purpose developer tool. `aos-check` remains the simple entry
surface while differentiated value is tested separately.


## Selected experiment: Change Proof plug-in

Control assurance is a low-frequency, potentially high-cost job and may be too
infrequent for daily developer value. The strongest current hypothesis is a
plug-in to the team's existing targeted tests:

> The tests pass, but would they still pass without the implementation change?

`prove-change` keeps PR tests, removes the selected implementation patch, and
runs the same verifier in clean worktrees. The result is bounded evidence that
the verifier is sensitive or insensitive to the actual patch. This complements
CI and coverage; it overlaps most closely with mutation testing and is not a
category-exclusive invention.

The exploratory benchmark produced correct, replayable mechanics in 8/8 cases
across five public repositories. Five real code-and-test PRs were
distinguished. Two behavior-preserving controls generated raw warnings that
would be noise if enabled indiscriminately; calibrated eligibility skipped
both. One under-scoped verifier was a controlled counterfactual, not an
observed user outcome. Median CLI time was 7.008 seconds for targeted tests.

Therefore the current decision is `CONTINUE_NARROW_PLUGIN_EXPERIMENT` and
`DO_NOT_ENABLE_BY_DEFAULT`. ROI remains unproven. Advancement requires at least
50 eligible external PRs across five repositories, warning acceptance of at
least 50%, noise and inconclusive rates no higher than 10% each, median added
time below two minutes, setup below ten minutes in 80% of repositories, a
merge-readiness or weak-test impact for at least 20% of accepted warnings, and
four-week retention in at least half of trial repositories. See the
[generated benchmark](../benchmarks/change-proof-plugin/REPORT.md).

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

- **Primary plug-in operator:** code author or reviewer responsible for tests,
  especially on agent-assisted PRs.
- **Control-assurance operator:** maintainer, platform engineer, or DevSecOps
  owner.
- **Potential buyer:** unvalidated; a team owner would need repeated accepted
  findings and measurable review or regression cost reduction.
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
| Low-friction technical path | No config, checkout, write scope, telemetry, runtime dependency, or account in the default path | [TRUST.md](TRUST.md) |
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
