# Hybrid Value Gate

This directory is the product-evidence claim gate. It keeps six claims
separate:

1. whether AOS computes information absent from the observed GitHub baseline;
2. whether that signal is valid, incremental, and sufficiently low-noise;
3. whether the product is internally ready for a user test;
4. whether practical-utility hypotheses are testable on stable product output;
5. whether an external user understands and benefits from it;
6. whether teams retain it in real work.

It does not issue a merge-readiness verdict.

## Current result

`NO_GO`.

- Mechanism evidence: `MECHANISM_CONFIRMED`.
- Signal validity: `SIGNAL_INCONCLUSIVE`.
- Internal product test: `PRODUCT_TEST_READY`.
- Practical-utility testability: `UTILITY_TEST_READY`.
- External-test readiness: `READY_FOR_EXTERNAL_VALIDATION`.
- Participant access: `RECRUITMENT_PENDING`.
- Validation distribution: `FREE_SELF_SERVE_VALIDATION`.
- External participants: currently unavailable.
- External teams: currently unavailable.
- External usability: `EXTERNAL_VALIDATION_PENDING`.
- Field utility: `FIELD_VALIDATION_PENDING`.

The prospective exact-SHA track contains three read-only observations across
three public repositories. In each, GitHub reported an open, non-draft PR as
`clean` with all observed checks successful, while AOS reported
`WARN/non_independent_evidence` because the same PR changed a workflow
that produced successful checks for that head SHA. Two cases retain canonical
bundle, policy, decision record, digests, and offline replay. In the strongest
case, the affected source was itself a required GitHub check.

This confirms a bounded semantic difference: GitHub reports check identity and
result; AOS additionally reports verifier independence. It does not establish
that the warning is actionable, low-noise, useful, or worth adopting.

The 100-PR discovery corpus establishes recurring candidate pain. It contains
no independently adjudicated exact-baseline outcomes. All three exact-SHA
outcomes also remain unresolved. Therefore neither corpus establishes
precision or product usefulness. Internal tests establish only product and
utility-test readiness. They are never user evidence.

## Evidence files

- `corpus.json` is the frozen public-metadata-only signal sample.
- `exact-contrasts.json` is the strict prospective exact-SHA corpus.
- `exact/` contains two canonical bundle/policy/decision-record triples.
- `EXACT_CONTRAST.md` states the mechanism proof and claim boundary.
- `product-test-readiness.json` binds B0 checks to executable evidence.
- `utility-task-corpus.json` freezes eight diagnosis tasks and controls.
- `utility-test-readiness.json` binds B0.5 checks to that corpus and tests and
  declares the free, public, advisory, telemetry-free validation channel.
- `HYBRID_PROTOCOL.md` freezes claim separation and deferred B1-B3 design.
- `assessment.json` is the deterministic machine-readable gate result.
- `ASSESSMENT.md` is its human-readable projection.

No code, diffs, logs, annotations, comment bodies, or commit messages are
stored in the signal research corpora.

## Reproduce

```bash
python tools/value_gate.py \
  --corpus benchmarks/value/corpus.json \
  --product-readiness benchmarks/value/product-test-readiness.json \
  --utility-readiness benchmarks/value/utility-test-readiness.json \
  --contrast-corpus benchmarks/value/exact-contrasts.json \
  --json-out benchmarks/value/assessment.json \
  --markdown-out benchmarks/value/ASSESSMENT.md
```

`--require-go` returns non-zero until product-claim criteria pass.

## Advancement rule

- `MECHANISM_CONFIRMED` proves only that AOS can produce decision-relevant
  information absent from the observed GitHub baseline.
- `MECHANISM_CONFIRMED + PRODUCT_TEST_READY + UTILITY_TEST_READY`, with
  no `SIGNAL_NOT_SUPPORTED` result, yields `READY_FOR_EXTERNAL_VALIDATION`.
  `SIGNAL_INCONCLUSIVE` may be resolved by that study.
- `READY_FOR_EXTERNAL_VALIDATION` permits recruitment and a controlled advisory
  study. It is not `PRODUCT_USEFUL`, paid-pilot readiness, or a production claim.
- `FREE_SELF_SERVE_VALIDATION` permits a public, no-cost advisory technical
  preview with no account or telemetry. Feedback and evidence submission are
  opt-in and user-controlled.
- `GO` additionally requires `SIGNAL_SUPPORTED` and independently supported
  external usability.
- Commercialization remains unvalidated until a separate field study
  establishes practical utility and retention.
- `NO_GO` blocks efficacy or value claims, production recommendations, and paid
  pilot intake. It does not block free advisory validation.

The free self-serve channel is open, while qualified participant evidence is
currently `RECRUITMENT_PENDING`. Availability, installs, downloads, and
unsolicited reactions are funnel observations, not evidence of usefulness or
market demand. A result qualifies only through a frozen external-study
contract with opt-in evidence bound to the tested version and task.

Formative usability requires 8-12
independent developers. Comparative testing and a 30-day, 5-10-team field
pilot remain
separate later stages. One-off reactions, maintainer dogfooding, AI-agent
simulations, and historical review comments cannot satisfy those stages. The
existing simple UX observation fields cannot produce a product-usefulness
claim; a versioned comparative-study contract must be frozen before enrollment.

The full protocol is [HYBRID_PROTOCOL.md](HYBRID_PROTOCOL.md). The corpus is
a bounded discovery sample, not a market study. It ranks no tools and supports
no security, compliance, ROI, defect-prevention, adoption, or
willingness-to-pay claim.
