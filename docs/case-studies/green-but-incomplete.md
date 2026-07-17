# Case Study: Green, but Incomplete

> **Historical explicit-policy example.** This committed record uses a
> policy that promotes every non-success advisory result to `WARN`. Current
> zero-config behavior still records a non-required skipped check but leaves
> it out of the verdict because GitHub already exposes it. A skipped check
> affects the default verdict only when it is required. This page proves
> policy-controlled visibility and replay, not the current first-run value
> proposition.
## The 60-second version

- Subject: this repository's own pull request head, pinned commit
  `9c064fc8c95d21453d553dc81e9a935ccfa54630` — a real change with a fully
  green dashboard.
- The catch: one control (`AOS Workflow Gate Self / no-checkout`) is
  skipped by design on pull requests — it never ran, and the dashboard
  looks identical to a run where it did.
- Result: the gate records verdict `WARN` over 4 real signals, naming the
  control that did not run, with a repair hint — instead of letting a
  skipped control hide behind green.
- Proof, offline on your machine:
  `aos-workflow-gate verify --input examples/green-but-incomplete-record.json
  --bundle examples/green-but-incomplete-bundle.json` prints `OK`.

## The problem this illustrates

A green dashboard answers "did the checks that ran pass?" It does not
answer "did everything that should protect this change actually run?"
Skipped and conditional checks render just like healthy ones at a glance.
This is exactly the class of gap that grows as pipelines get more
conditional — and as more changes originate from AI agents whose authors
cannot vouch for the pipeline themselves.

## What the gate recorded

From the committed record
([examples/green-but-incomplete-record.json](../../examples/green-but-incomplete-record.json)):

| Measure | Value |
| --- | --- |
| Verdict | `WARN` |
| Signals gated | 4 (1 required, 3 advisory) |
| Controls that never ran | 1 (`skipped`, named in the reasons with a repair hint) |
| Time to verdict (offline evaluate, cold process) | ~1.4 s |
| Replay | `OK` from the committed files, no network |

The reason line in the record is explicit:
`advisory_warning … advisory source status is 'skipped'` — the record
distinguishes *did not run* from *ran and passed*, which the dashboard
does not.

## Method

The bundle was collected from the GitHub check-runs API for the pinned
commit with `collect` (the same digest recipe as the
[first case study](aos-kernel-release-surface-replay.md); anyone can
re-fetch and recompute). The policy was generated with the required check
mirroring this repository's own branch protection. Both are committed, so
the decision replays offline and is re-verified by CI on every push
(`tests/test_fixtures_replay.py`).

## Boundary

The skipped control here is skipped **by design** on pull requests; this
study shows visibility, not a vulnerability, and makes no security claim
about any repository. `WARN` means exactly what the policy says it means:
an advisory source was not successful. Decision records remain
`UNSIGNED_NOT_OFFICIAL`.
