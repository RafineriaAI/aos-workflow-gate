# Hybrid Value Gate

This directory is the pre-publication product gate. It keeps four claims
separate:

1. whether an AOS signal is valid and incremental;
2. whether the product is internally ready for a user test;
3. whether an external user understands and benefits from it;
4. whether teams retain it in real work.

It does not issue a merge-readiness verdict.

## Current result

`NO_GO`.

- Signal validity: `SIGNAL_INCONCLUSIVE`.
- Internal product test: `PRODUCT_TEST_READY`.
- External participants: currently unavailable.
- External teams: currently unavailable.
- External usability: `EXTERNAL_VALIDATION_PENDING`.
- Field utility: `FIELD_VALIDATION_PENDING`.

The 100-PR discovery corpus establishes recurring candidate pain. It does
not contain independently adjudicated exact-baseline outcomes and therefore
cannot establish precision or usefulness. Internal tests can establish only
that the product is ready to test. They are never user evidence.

## Evidence files

- `corpus.json` is the frozen public-metadata-only signal sample.
- `product-test-readiness.json` binds B0 checks to executable evidence.
- `HYBRID_PROTOCOL.md` freezes the claim separation and deferred B1-B3 design.
- `assessment.json` is the deterministic machine-readable gate result.
- `ASSESSMENT.md` is its human-readable projection.

No code, diffs, logs, annotations, comment bodies, or commit messages are
stored in the discovery corpus.

## Reproduce

```bash
python tools/value_gate.py \
  --corpus benchmarks/value/corpus.json \
  --product-readiness benchmarks/value/product-test-readiness.json \
  --json-out benchmarks/value/assessment.json \
  --markdown-out benchmarks/value/ASSESSMENT.md
```

`--require-go` returns non-zero until publication criteria pass.

## Advancement rule

- `SIGNAL_SUPPORTED + PRODUCT_TEST_READY` permits only a controlled external
  study. It does not permit product publication.
- `GO` additionally requires `EXTERNAL_USABILITY_SUPPORTED`.
- Commercialization remains unvalidated until a separate field study
  establishes practical utility and retention.
- `NO_GO` blocks publication, marketing, production recommendations, and paid
  pilot intake.

When access becomes available, formative usability requires 8-12 independent
developers. Comparative testing and a 30-day, 5-10-team field pilot remain
separate later stages. One-off reactions, maintainer dogfooding, AI-agent
simulations, and historical review comments cannot satisfy those stages. The
existing simple UX observation fields cannot produce a product-usefulness claim;
a versioned comparative-study contract must be frozen before enrollment.

The full protocol is [HYBRID_PROTOCOL.md](HYBRID_PROTOCOL.md). The corpus is
a bounded discovery sample, not a market study. It ranks no tools and
supports no security, compliance, ROI, defect-prevention, adoption, or
willingness-to-pay claim.
