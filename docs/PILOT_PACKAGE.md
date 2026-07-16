# Evidence-Led Pilot Package

**Status: intake closed.** This is the future handover specification,
not an active offer. Pilot publication remains blocked by the
[`NO_GO` Value Gate](../benchmarks/value/ASSESSMENT.md).


What a future guided pilot would hand over, file by file. "Evidence-led"
means every claim in the final report would be an artifact the customer
can replay without us.

## Deliverables

| Artifact | Format | The customer can verify it by |
| --- | --- | --- |
| Gate policy for the piloted workflow | policy YAML/JSON (theirs to keep) | reading it; its digest is embedded in every record |
| Decision records — advisory phase | one JSON record per gated change | `verify --input --bundle` offline |
| Decision records — enforcement phase | records with `can_block: true` | same replay, plus the CI run that failed on `BLOCK` |
| Signal bundles and generated policies | JSON next to each record | recomputing digests from their own CI state |
| Measured results table | Markdown, the [VALUE_METRICS](VALUE_METRICS.md) template on their data | re-running the commands in the table |
| in-toto Statement exports | one per key record, unsigned | signing with their own keys ([DECISION_PREDICATE](DECISION_PREDICATE.md)) |
| Runbook | Markdown: how to run, extend, and replay without us | following it end to end |
| Pilot report | [the template](templates/PILOT_REPORT_TEMPLATE.md), filled | every number links to an artifact above |

## Handover checklist

- [ ] All artifacts live in the customer's repository or storage — nothing
      is retained on our side.
- [ ] Every record replays offline on a customer machine (witnessed).
- [ ] The enforcement decision (stay advisory / enforce which checks) is
      the customer's, recorded in the report.
- [ ] NDA-covered material identified and excluded from anything public.
- [ ] Case-study permission asked separately in writing, or not at all.

## Boundary

The package proves what the tooling proves: deterministic, replayable,
tamper-evident gate decisions over an explicit policy on the piloted
workflow. It is not a security audit, not a compliance certification, and
carries no ROI arithmetic ([VALUE_METRICS](VALUE_METRICS.md) explains
why). Decision records remain `UNSIGNED_NOT_OFFICIAL`.
