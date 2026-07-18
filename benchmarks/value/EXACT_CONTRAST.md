# Exact-SHA semantic contrast

## Result

Three prospective, read-only cases across three public repositories have the
same mechanical shape:

```text
exact head SHA
+ GitHub merge state CLEAN
+ every observed GitHub check run successful
+ a workflow changed by the PR produced successful checks for that PR
= AOS WARN: non_independent_evidence
```

Two cases were collected end to end by `aos-workflow-gate check-pr` and retain
canonical bundle, policy, decision record, digests, and offline replay. The
third was evaluated from live API facts through the deterministic verifier-
change engine; its full CLI collection was prevented by the anonymous GitHub
API limit and is therefore not represented as a canonical record.

The sharpest case is
[`scramble-robot/questix#99`](https://github.com/scramble-robot/questix/pull/99):
GitHub reported `clean`, while the required `build-summary` check came from
`.github/workflows/ros2-build-test-skipped.yaml`, which the same PR changed.
GitHub validated the check context, app identity, and success. AOS additionally
linked the check suite to the modified verifier and named the evidence as
non-independent.

## What this proves

- AOS produces deterministic information not present in GitHub's green/clean
  baseline: whether successful evidence was produced by a verifier changed by
  the same PR.
- The contrast works on exact SHA and names affected checks and workflows.
- Two decision records replay offline against committed bundles and policies.

## What this does not prove

- That every warning is actionable.
- Low false-positive rate, defect prevention, time savings, ROI, demand, or
  willingness to pay.
- That `clean` is full organizational merge readiness; bypass actors and some
  non-status controls remain outside the public observation boundary.
- Replayability of the search funnel; its counts are an operator-attested
  point-in-time observation, not a committed raw result set.
- GitHub authorship of the snapshot. Public API observations are committed but
  not signed by GitHub.

The outcomes remain `unresolved`. These cases establish technical semantic
advantage, not product-publication readiness. Independent adjudication is still
required for the precision denominator.

## Reproduce

```bash
python -m aos_workflow_gate verify \
  --input benchmarks/value/exact/geotab-mygeotab-python-240/gate-decision.json \
  --bundle benchmarks/value/exact/geotab-mygeotab-python-240/bundle.json

python -m aos_workflow_gate verify \
  --input benchmarks/value/exact/hardware-abstraction-ir-62/gate-decision.json \
  --bundle benchmarks/value/exact/hardware-abstraction-ir-62/bundle.json
```

GitHub documents `CLEAN` as mergeable with passing commit status and notes that
skipped jobs can report success. SLSA separately models the build control plane
as trusted infrastructure outside tenant control. Those references motivate
the distinction; they do not label these individual warnings as useful:

- <https://docs.github.com/en/graphql/reference/pulls#mergestatestatus>
- <https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/about-status-checks>
- <https://slsa.dev/spec/v1.2/build-provenance>
