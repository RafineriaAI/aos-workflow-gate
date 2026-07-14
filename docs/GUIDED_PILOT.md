# Guided Pilot

**Status: intake closed.** This is a future engagement specification.
The [Incremental Value Gate](../benchmarks/value/ASSESSMENT.md) is
`NO_GO`; no paid pilot or design-partner offer is active.


The future engagement would take one real workflow from "green checks"
to a replayable, enforceable gate decision. The repository remains
Apache-2.0 with no feature gates; any future fee would cover guidance,
policy design, and evaluation on customer-controlled data.

## Future path

0. **Internal readiness gate** — maintainers reproduce the
   [Value Gate](../benchmarks/value/README.md). No external qualification
   or intake path opens before `GO`.
1. **Scoping** — intake opens only after the Value Gate reaches `GO`.
   Scope, price, timeline, and data boundaries would be agreed in writing
   before any work starts.
2. **Policy design** — we translate how you already protect the workflow
   (required checks, scanners, agent review) into an explicit, inspectable
   gate policy.
3. **Wiring** — the action or CLI runs in your environment, on your
   runners, under read-only scopes; nothing leaves your side.
4. **Measured results** — replayable decision records for real changes,
   with time-to-verdict, replay success, and required-check coverage.
5. **Handover** — the policy, the records, and the runbook stay yours.
   No lock-in: everything keeps working without us.

Confidentiality: a mutual NDA before any non-public material; your
signals and results are your confidential information.

The full deliverable set, file by file, with the handover checklist, is
defined in [PILOT_PACKAGE.md](PILOT_PACKAGE.md); the report follows
[a fixed template](templates/PILOT_REPORT_TEMPLATE.md) where every number
links to a replayable artifact.

## Future design-partner variant

After `GO`, a bounded design-partner engagement may exchange structured
feedback for reduced scope. A referenceable case study would still require
separate written approval. No design-partner intake is active.

## Boundaries

The pilot does not deliver a security audit, compliance certification,
signed or official verdicts, or any production guarantee. Decision records
remain `UNSIGNED_NOT_OFFICIAL`. What it delivers is exactly what the
public tooling proves: deterministic, replayable, tamper-evident gate
decisions over your explicit policy.
