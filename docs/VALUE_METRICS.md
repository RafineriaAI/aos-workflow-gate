# Value Metrics

Mechanism results and product outcomes are reported separately. Committed
records prove deterministic evaluation and replay; they do not by themselves
prove that a maintainer would act, change a merge decision, retain the tool, or
pay for it.

## Committed evidence

| Evidence | Verdict | Outcome | What it supports |
| --- | --- | --- | --- |
| [Release-surface replay](case-studies/aos-kernel-release-surface-replay.md) | `PASS` | `not_applicable` | Exact-SHA collection, policy binding, and offline replay. |
| [Expected skipped check](case-studies/green-but-incomplete.md) | historical `WARN` | `noise` | A technically correct status can still be operationally irrelevant. Current zero-config defaults keep this case quiet. |
| [v0.11.0 incident counterfactual](../benchmarks/cases/v0110-incident-counterfactual/) | `BLOCK` | `supporting_evidence` | Real failed self-tests align with a real broken release; AOS-driven decision change was not observed. |

The expected-skip record remains unchanged so historical replay is honest. It
is excluded from precision, actionable-rate, incremental-value, and advantage
claims. The incident is supporting evidence for mechanism relevance, but its intervention is
counterfactual because AOS was not active at the time.

## What is measured

- exact persisted signals and record digests;
- deterministic policy outcome;
- offline replay;
- explicit outcome classification and whether maintainer action or AOS-driven
  decision change was observed.

These mechanism fields are counted, not estimated. No page-count or time-saved proxy is treated as business value.

## Local Project Check engineering remeasurement

The frozen exact-SHA corpus contained 60 earlier root-only missing-test
warnings. Metadata-only reconstruction found a declared nested test command in
8 cases (13.3%); 7 (11.7%) also completed the bounded nested search. Among 12
cases previously adjudicated as containing definite test material, 5 exposed a
supported command and 4 also completed bounded discovery.

This demonstrates a reduction in one known false-warning mechanism. Repository
code was not executed, so the result does not establish that tests pass, cover
business behavior, change a maintainer decision, produce retention, or justify
payment. [Inspect the report](../benchmarks/mass-market/PROJECT_CHECK_REMEASUREMENT.md).

## Required external field metrics

The committed studies do not measure product utility. External validation must
separate alert volume from business relevance and report at least:

| Metric | Decision question |
| --- | --- |
| Actionable rate | Did the maintainer perform the named remediation? |
| Decision-change rate | Did AOS change merge, review, or escalation behavior? |
| Incremental finding rate | Did AOS reveal a gap absent from GitHub's baseline and a naive workflow-change rule? |
| Alert acceptance and repeated-alert rate | Was the recommendation accepted, and did unresolved noise repeat? |
| Independently adjudicated noise | Was the signal technically correct but operationally irrelevant? |
| Time-to-resolution | How long from alert to accepted remediation or documented override? |
| Evidence-handling time | Did replayable evidence reduce investigation or assurance preparation time? |
| Control-drift and exception closure | Did an owner restore or explicitly accept a changed control? |
| Activation and 30-day retention | Did an external team keep the Action enabled after repeated runs? |
| Repository expansion and willingness to pay | Did the control owner extend use and fund organization-level operation? |

No metric may be inferred from stars, downloads, passing tests, internal
benchmarks, or the number of generated alerts.

### Additional metrics for executable change proof

| Metric | Decision question |
| --- | --- |
| Eligible-change coverage | What share of real PRs can be assessed without manual path or environment repair? |
| Change-sensitive rate | How often do green checks fail after the implementation patch is removed? |
| Insensitive-test acceptance | How often does `change_not_distinguished` lead to a stronger test, documented exception, or changed merge decision? |
| Incremental lift over mutation testing | Does AOS find accepted gaps not already found by the team's mutation or coverage tooling? |
| Inconclusive and flaky-repeat rate | How often do environment, patch, timeout, or nondeterministic results prevent a stable answer? |
| Runtime and compute overhead | Added wall time and runner cost per eligible PR and per accepted finding. |
| Avoided-review-work proxy | Did the executable result replace a reviewer request for proof, or shorten the thread to acceptance? |

Report these separately by language, test framework, change size, agent versus
human author, and selected-path strategy. A high insensitive rate is not
automatically value; without accepted remediation it may be noise.

## What we deliberately do not compute

No return-on-investment figure, no hours-saved estimate, no incident
probability, and no monetary risk reduction. Those depend on a team's rates,
incident history, control ownership, and assurance regime - numbers we do not
have and will not invent. A future external study, after the applicable Value
Gate opens, must measure these outcomes on user workflows. Pilot intake is
currently closed.

## Boundary

These metrics describe evidence handling, not protection quality: a fast,
replayable `PASS` does not make the underlying checks good. Decision
records remain `UNSIGNED_NOT_OFFICIAL`.
