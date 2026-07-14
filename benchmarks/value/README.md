# Incremental Value Gate

This directory is a pre-publication product gate. It asks whether AOS has
shown useful, incremental signal beyond GitHub's exact decision baseline
with sufficiently low noise, and whether an external user can understand
and act on the result. It does not issue a merge-readiness verdict.

## Current result

`NO_GO`. Do not publish, market, or start an external pilot from this
evidence. The technical implementation may be evaluated internally in
advisory mode.

The committed sample contains public metadata for 100 recently merged pull
requests across 10 repositories. Collection was complete for all 100 cases.
Seven PRs across five repositories changed a workflow that also evaluated
that change; two of the seven were bot-authored. Keyword matching found
22 CI/test-related inline review comments across 12 PRs.

Those observations establish recurring candidate pain, not product value:

- No retrospective case has an exact-SHA GitHub merge-readiness snapshot.
- No signal case has an independent actionable/noise outcome label.
- Historical check conclusions do not prove what GitHub permitted at merge.
- Operator judgment cannot be used to compute product precision.
- External comprehension, remediation success, and retention are untested.

The observed review history points to everyday gaps around test adequacy,
selective-CI path coverage, public-API impact, manual test evidence, and
workflow security rationale. A policy for any of these gaps remains out of
scope until it can be specified deterministically and shown to be low-noise.

## Files

- `corpus.json` is the frozen, public-metadata-only sample. It contains no
  code, diffs, logs, annotations, comment bodies, or commit messages.
- `assessment.json` is the deterministic machine-readable decision.
- `ASSESSMENT.md` is a projection of the same decision for maintainers.

## Reproduce

```bash
python tools/value_gate.py \
  --corpus benchmarks/value/corpus.json \
  --json-out benchmarks/value/assessment.json \
  --markdown-out benchmarks/value/ASSESSMENT.md
```

`--require-go` returns non-zero unless every technical-value and external-
usability criterion passes. `GO`, `CONDITIONAL_GO`, and `NO_GO` are product
release states; they are deliberately distinct from AOS
`PASS`/`WARN`/`BLOCK` verdicts.

## Advancement rule

- `NO_GO`: publication and external pilot intake stay closed.
- `CONDITIONAL_GO`: technical value is demonstrated; a controlled external
  usability test may start.
- `GO`: technical value and external usability both meet the predeclared
  thresholds in `tools/value_gate.py`.

A qualified external user has completed at least three real gate runs and
kept the gate enabled for at least seven days. `GO` requires five such
users; one-off reactions do not count as usability or retention evidence.

The corpus is a bounded sample, not a market study. It ranks no tools and
supports no security, compliance, ROI, or defect-prevention claim.
