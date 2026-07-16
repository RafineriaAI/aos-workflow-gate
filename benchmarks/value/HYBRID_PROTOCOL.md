# Hybrid Signal and Product Study

**Status: free self-serve validation available; qualified recruitment pending.**

No external developers or teams are currently enrolled. Internal evidence
establishes that the product and its practical-utility hypotheses are testable,
so a free public advisory channel is available without an account or telemetry.
It does not establish comprehension, usefulness, low noise, adoption,
retention, ROI, or willingness to pay. Product claims, production
recommendations, and paid pilot intake remain closed.

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

Current mechanism evidence comprises three prospective exact-SHA cases across
three repositories. It establishes only that AOS can identify verifier
non-independence absent from the observed GitHub green/clean baseline. Two
cases retain canonical replay artifacts. No case has an independently
adjudicated outcome; therefore the mechanism is `MECHANISM_CONFIRMED`
while signal validity remains `SIGNAL_INCONCLUSIVE`.

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

### B0.5. Practical-utility testability

The content-addressed `utility-task-corpus-v0` freezes eight internal tasks:
two positive controls and six non-PASS controls spanning required-check
success, zero requirements, missing/failed/unverifiable controls, incomplete
collection, and exact-SHA verifier non-independence. Each task binds the
expected verdict, advisory effect, primary reason, remediation code, evidence
integrity, and exactly one `Next`.

Passing B0.5 yields `UTILITY_TEST_READY`. It means only that an external
participant can be tested against stable product output. Simulated tasks,
maintainers, tests, and AI agents cannot yield `PRODUCT_USEFUL`.

### B0.75. Validation distribution posture

`FREE_SELF_SERVE_VALIDATION` requires `READY_FOR_EXTERNAL_VALIDATION` plus a
strict manifest declaration of free access, public self-service, advisory
effect, and no telemetry. It opens a technical preview and opt-in feedback
channel; it does not add evidence to the signal, usability, or field tracks.

Installs, downloads, issue traffic, and unsolicited reactions are funnel
observations. A usability outcome qualifies only under a frozen protocol with
consent and evidence bound to the tested version, task, and result. Free access
cannot measure willingness to pay and introduces self-selection bias.

### B1. Formative usability - recruitment pending

Entry requires `MECHANISM_CONFIRMED`, `PRODUCT_TEST_READY`,
`UTILITY_TEST_READY`, and no `SIGNAL_NOT_SUPPORTED` result. This deliberately
allows `SIGNAL_INCONCLUSIVE`: independent outcomes from the study are needed
to resolve it. Recruit 8-12 independent developers when qualified access exists. Use
frozen, balanced tasks; measure comprehension, correct next action, time, and
trust calibration. Findings are formative and do not prove market demand.

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

| Mechanism | Signal | Product test | Utility test | Participants | Decision |
| --- | --- | --- | --- | --- | --- |
| confirmed | inconclusive | ready | ready | unavailable | `FREE_SELF_SERVE_VALIDATION`; qualified recruitment pending; product claims `NO_GO` |
| confirmed | inconclusive/supported | ready | ready | available | controlled advisory study; product claims `NO_GO` |
| confirmed | supported | ready | ready | usability supported | limited-release candidate |
| incomplete | any | any | any | any | validation distribution and product claims `NO_GO` |
| any | unsupported | any | any | any | validation distribution and product claims `NO_GO` |
| any | any | incomplete | incomplete/any | any | validation distribution and product claims `NO_GO` |

Commercialization remains unvalidated until field utility and retention are
observed. Free availability, installs, downloads, a green test suite,
replayable evidence, or historical review agreement cannot establish product
usefulness by itself.

## Current state

- Mechanism evidence: `MECHANISM_CONFIRMED`.
- Signal validity: `SIGNAL_INCONCLUSIVE`.
- Internal product test: `PRODUCT_TEST_READY`.
- Practical-utility testability: `UTILITY_TEST_READY`.
- External-test readiness: `READY_FOR_EXTERNAL_VALIDATION`.
- Participant access: `RECRUITMENT_PENDING`.
- Validation distribution: `FREE_SELF_SERVE_VALIDATION`.
- External participants: unavailable.
- External teams: unavailable.
- External usability: `EXTERNAL_VALIDATION_PENDING`.
- Field utility: `FIELD_VALIDATION_PENDING`.
- Product claims and paid pilots: `NO_GO`.
