# Value Metrics

Operational friction, measured — not modeled. Every number below is
counted, not estimated, and comes from the two committed case studies,
reproducible offline from files in this repository and re-verified by CI
on every push (`tests/test_fixtures_replay.py`).

## Measured values

| Metric | [Study 1: release-surface replay](case-studies/aos-kernel-release-surface-replay.md) | [Study 2: green-but-incomplete](case-studies/green-but-incomplete.md) |
| --- | --- | --- |
| Verdict | `PASS` | `WARN` |
| Signals gated | 5 (1 required, 4 advisory) | 4 (1 required, 3 advisory) |
| Controls that never ran, surfaced by name | 0 | 1 |
| Time to verdict (whole process, cold start) | ~0.4 s | ~1.4 s |
| Offline replay of the committed record | `OK` | `OK` |
| Policy expressed as an inspectable artifact | yes (mirrors the repo's branch ruleset) | yes (generated, committed) |

## The friction proxy

To answer *"why did this gate pass?"* without the gate, a reviewer opens
one page per check run (5 and 4 pages respectively in the studies), plus
the branch-protection settings, and still has no artifact to hand to a
second reviewer. With the gate the same answer is **one committed record
plus one replay command** — and the record additionally distinguishes
*did not run* from *ran and passed*, which no dashboard page shows at a
glance. We count surfaces (pages vs files); we do not convert them into
minutes or money.

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
