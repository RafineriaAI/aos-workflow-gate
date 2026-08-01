# Release Maturity

Current maturity: **Preview**.

Published version: **v0.38.0**. Distribution is free, public, self-serve, and
advisory by default. Preview means: try it, check whether the warning helped,
and report what happened. Do not let it block production changes without human
review.

The mechanism is tested. Everyday value is not proven. The GitHub-gate holdout
found no new action matching material reviewer problems in ten real pull
requests. The Change Proof plug-in experiment passed mechanics in 8/8 cases,
but also showed raw noise in 2/2 behavior-preserving controls and observed no
external accepted warning or decision change. Keep it opt-in and narrowly
eligible. See [Change Proof](../benchmarks/change-proof-plugin/REPORT.md) and
[Should AOS continue?](../benchmarks/adaptive-value-calibration/REPORT.md).

The machine-readable declaration is
[RELEASE_STATUS.json](RELEASE_STATUS.json). Release checks require it to
match [PUBLISHED_VERSION](PUBLISHED_VERSION).

## Levels

| Level | Meaning |
| --- | --- |
| **Preview** | The mechanism is usable and tested, but material false positives, incomplete coverage, or workflow-specific limitations may remain. No production recommendation. |
| **Pilot** | Suitable for controlled repositories with a named owner, monitoring, an override path, and rollback. Findings and ignored alerts are measured. |
| **Production candidate** | Stable contracts, documented limitations, representative operational tests, and public external measurements support broader evaluation. |
| **Production ready** | Independent use confirms operational reliability; support, incident response, recovery, compatibility, and release procedures are active. |

## Promotion Gates

Tests cannot promote maturity by themselves.

### Preview to Pilot

All are required:

1. no unresolved critical correctness or security issue;
2. the operational matrix passes on every supported Python boundary;
3. every non-PASS result keeps Reason + Impact + Next step + Severity;
4. at least one independent controlled deployment completes with a named
   owner, rollback path, and recorded accepted/ignored findings;
5. known limitations and false positives are public;
6. Change Proof, if included, is opt-in and limited to code-and-test changes or
   an explicitly declared behavior-sensitive verifier.

### Pilot to Production Candidate

All are required:

1. versioned contracts have a documented compatibility and migration policy;
2. representative external repositories cover the supported GitHub workflow
   matrix;
3. preregistered measurements report precision, false-positive rate,
   actionable rate, alert acceptance, decision change, time to resolution,
   and retention;
4. the evidence supports the published thresholds and claim boundary;
5. installation, rollback, security, and support procedures are exercised.

### Production Candidate to Production Ready

All are required:

1. multiple independent teams retain the product in real workflows;
2. an operational reliability target and incident-response procedure are
   measured and met;
3. upgrade, rollback, recovery, and compatibility exercises pass;
4. a maintained support channel and release ownership exist;
5. no NO_GO condition conflicts with the production claim.

A release may remain at the same level or be downgraded. Promotion requires
reviewed evidence and an explicit change to the release-status declaration.
