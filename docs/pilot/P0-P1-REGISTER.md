# P0/P1 Register — release correctness and collection consistency

The single source of truth for known correctness-critical findings on
the road to the external pilot. An item enters as soon as it is known;
it leaves only with a named resolution. Severities: **P0** — wrong
verdict or broken evidence chain possible; **P1** — a public path is
broken or a claim is unsupported; **P2** — residual, documented risk.

| Id | Severity | Finding | Resolution | Status |
| --- | --- | --- | --- | --- |
| REL-1 | P1 | Public quickstarts referenced `@v0.30.0` while no `v0.30.0` tag existed (merged, never tagged or released) — every copy-paste install failed. | Retroactive tag `v0.30.0` on the exact merged commit, Release Gate verified green, release published with replayable evidence. | **Closed** |
| COL-1 | P1 | Two entry points (`run --github-context` discovery and `check-pr`) could in principle classify the same GitHub state differently after the parallel #47/#48 × #49/#54 merge — two truths. | Both paths audited onto the one shared requirement snapshot; a consistency E2E (`tests/test_collection_consistency.py`) pins identical classification, rules digest, visibility evidence, and verdict for one identical fake state, on every CI run. | **Closed** |
| ID-1 | P2 | New evidence families from #49–#54 (workflow visibility, verifier-change) audited against the identity-completeness invariant. | No violation: they are collection-level evidence (digest-anchored through the bundle), not bundle sources; determinations are pure functions of observed facts with no model output in any verdict path. | **Closed (no defect)** |
| OPS-1 | P2 | CI has two check suites per head; a waiter that samples early can see one complete suite and act before the second exists (nearly caused a premature merge once). | Maintainer-side protocol: merge only after the full expected run set (≥6 runs) is completed and green; encoded in the operating notes. Product unaffected. | **Closed (procedural)** |
| BUD-1 | P2 | Discovery + visibility + statuses + suites consume more API calls per run than the pre-#49 collector; pathological repositories could approach the 50-call budget. | Budgets unchanged and enforced (operational error, never a verdict); residual documented here. Raise `--max-api-calls` if a legitimate repository trips it. | **Accepted residual** |

No open P0. No open P1.
