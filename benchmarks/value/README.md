# Hybrid Value Gate

This directory is the pre-publication product gate. It keeps five claims
separate:

1. whether AOS computes information absent from the observed GitHub baseline;
2. whether that signal is valid, incremental, and sufficiently low-noise;
3. whether the product is internally ready for a user test;
4. whether an external user understands and benefits from it;
5. whether teams retain it in real work.

It does not issue a merge-readiness verdict.

## Current result

`NO_GO`.

- Mechanism evidence: `MECHANISM_CONFIRMED`.
- Signal validity: `SIGNAL_INCONCLUSIVE`.
- Internal product test: `PRODUCT_TEST_READY`.
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
precision or product usefulness. Internal tests can establish only that the
product is ready to test. They are never user evidence.

## Evidence files

- `corpus.json` is the frozen public-metadata-only signal sample.
- `exact-contrasts.json` is the strict prospective exact-SHA corpus.
- `exact/` contains two canonical bundle/policy/decision-record triples.
- `EXACT_CONTRAST.md` states the mechanism proof and claim boundary.
- `product-test-readiness.json` binds B0 checks to executable evidence.
- `HYBRID_PROTOCOL.md` freezes claim separation and deferred B1-B3 design.
- `assessment.json` is the deterministic machine-readable gate result.
- `ASSESSMENT.md` is its human-readable projection.

No code, diffs, logs, annotations, comment bodies, or commit messages are
stored in either research corpus.

## Reproduce

```bash
python tools/value_gate.py \
  --corpus benchmarks/value/corpus.json \
  --product-readiness benchmarks/value/product-test-readiness.json \
  --contrast-corpus benchmarks/value/exact-contrasts.json \
  --json-out benchmarks/value/assessment.json \
  --markdown-out benchmarks/value/ASSESSMENT.md
```

`--require-go` returns non-zero until publication criteria pass.

## Advancement rule

- `MECHANISM_CONFIRMED` proves only that AOS can produce decision-relevant
  information absent from the observed GitHub baseline.
- `MECHANISM_CONFIRMED + SIGNAL_SUPPORTED + PRODUCT_TEST_READY` permits
  only a controlled external study. It does not permit product publication.
- `GO` additionally requires `EXTERNAL_USABILITY_SUPPORTED`.
- Commercialization remains unvalidated until a separate field study
  establishes practical utility and retention.
- `NO_GO` blocks publication, marketing, production recommendations, and
  paid pilot intake.

When access becomes available, formative usability requires 8-12 independent
developers. Comparative testing and a 30-day, 5-10-team field pilot remain
separate later stages. One-off reactions, maintainer dogfooding, AI-agent
simulations, and historical review comments cannot satisfy those stages. The
existing simple UX observation fields cannot produce a product-usefulness
claim; a versioned comparative-study contract must be frozen before enrollment.

The full protocol is [HYBRID_PROTOCOL.md](HYBRID_PROTOCOL.md). The corpus is
a bounded discovery sample, not a market study. It ranks no tools and supports
no security, compliance, ROI, defect-prevention, adoption, or
willingness-to-pay claim.
