# Hybrid Signal and Product Study

**Status: preregistered execution framework; external validation pending.**

No external developers or teams are currently available. This does not block
signal research or internal product-test readiness. It is a hard boundary
against claims about product usefulness, adoption, retention, or willingness
to pay.

## Independent tracks

### A. Signal validity

Question: does `non_independent_evidence` identify an exact-SHA evidence gap
and add information beyond the observed GitHub baseline?

The primary evidence is prospective and exact-SHA. Public review history is
secondary concordance evidence, never a substitute for random alert
verification. Repository is the statistical cluster. Discovery and holdout
must be split by repository or repository family. Selection, cutoff,
stopping, censoring, labels, reviewer assignment, prompts, seeds, and the
manifest digest must be frozen before holdout analysis.

Outcomes remain separate:

- factual signal correctness;
- expert actionability;
- historical-review concordance;
- behavior change.

A signal can reach `SIGNAL_SUPPORTED` only from independently adjudicated
exact-baseline evidence with the frozen precision and repository-diversity
thresholds. Insufficient outcome coverage is `SIGNAL_INCONCLUSIVE`, not
noise.

### B0. Product-test readiness

This track verifies only that the product is ready to place in front of a
participant:

- isolated wheel installation and CLI startup;
- executable first-run path;
- deterministic `Verdict + Reason + Next` output;
- frozen `PASS/WARN/BLOCK` task corpus;
- adversarial and misleading-state coverage;
- frozen external-study procedure.

Passing B0 yields `PRODUCT_TEST_READY`. Automated tests, maintainers, and AI
agents are not users and cannot yield `PRODUCT_USEFUL`.

### B1. Formative usability - deferred

Recruit 8-12 independent developers after A and B0 permit a controlled
study. Use frozen, balanced tasks. Measure comprehension, correct next
action, time, and trust calibration. Findings are formative and do not prove
market demand.

### B2. Comparative usability - deferred

Randomize matched cases between `GitHub/CI only` and `GitHub/CI + AOS`.
Freeze the primary endpoint before enrollment. Measure correct merge-readiness
decisions, gap detection, false blocking, next-action correctness, and time.
Do not expose AOS labels or expected outcomes to participants. A versioned
observation and analysis contract must be frozen before the first participant.
The existing simple UX observation fields are legacy planning inputs and cannot
satisfy this comparative-study requirement.

### B3. Field utility - deferred

Run an advisory-only 30-day closed pilot with 5-10 independent teams.
Measure retained enablement, dismissals, overrides, actions after alerts,
disable reasons, and repeated value. Willingness to pay requires behavioral
or transaction evidence and remains separate from usability.

## Decision firewall

| Signal | Product test | External usability | Decision |
| --- | --- | --- | --- |
| supported | ready | pending | controlled external study only |
| supported | ready | supported | limited-release candidate |
| unsupported | any | any | `NO_GO` |
| inconclusive | any | any | extend the frozen study; no claim |

Commercialization remains unvalidated until field utility and retention are
observed. Availability of source code, a green test suite, replayable
evidence, or historical review agreement cannot open publication by itself.

## Current state

- Signal validity: `SIGNAL_INCONCLUSIVE`.
- Internal product test: `PRODUCT_TEST_READY`.
- External participants: unavailable.
- External teams: unavailable.
- External usability: `EXTERNAL_VALIDATION_PENDING`.
- Field utility: `FIELD_VALIDATION_PENDING`.
- Publication: `NO_GO`.
