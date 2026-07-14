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

## What we deliberately do not compute

No return-on-investment figure, no hours-saved estimate, no incident
probability, and no monetary risk reduction. Those depend on your team's
rates, incident history, and audit regime — numbers we do not have and
will not invent. A future [guided pilot](GUIDED_PILOT.md), after the
pre-publication Value Gate reaches `GO`, would measure the same operational
metrics on customer workflows and leave the arithmetic to the customer.
Pilot intake is currently closed.

## Boundary

These metrics describe evidence handling, not protection quality: a fast,
replayable `PASS` does not make the underlying checks good. Decision
records remain `UNSIGNED_NOT_OFFICIAL`.
