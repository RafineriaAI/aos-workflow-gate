# Pilot Report — {{CUSTOMER}} / {{WORKFLOW}}

Scope reference: {{SCOPING_ISSUE_LINK}}. Period: {{START}} – {{END}}.
Every number below links to a committed artifact; replay instructions are
in the runbook.

## What was gated

- Workflow: {{WORKFLOW_DESCRIPTION}}
- Policy: `{{POLICY_FILE}}` (digest `{{POLICY_DIGEST}}`), designed from
  {{POLICY_SOURCE, e.g. the branch ruleset and scanner set}}.
- Phases: advisory {{N_ADVISORY}} changes; enforcement {{N_ENFORCED}}
  changes.

## Measured results (counted, not estimated)

| Metric | Value | Artifact |
| --- | --- | --- |
| Changes gated | {{N}} | records index |
| Verdicts (PASS/WARN/BLOCK) | {{P}}/{{W}}/{{B}} | per-record |
| Controls that never ran, surfaced by name | {{K}} | records: reasons |
| Median time to verdict | {{T}} | collection metadata |
| Offline replay success | {{N}}/{{N}} | witnessed on {{DATE}} |
| Enforced BLOCKs that stopped a merge | {{B_ENFORCED}} | CI run links |

## Decision gaps found and closed

{{LIST: gap → policy change → evidence}}

## What stays with you

Policy, records, bundles, exports, runbook — everything keeps working
without RafineriaAI. Suggested next steps: {{NEXT}}.

## Boundary

This report describes evidence handling on the piloted workflow only. It
makes no security-audit, compliance, or ROI claim; a `PASS` means the
explicit policy was satisfied — nothing more. Records remain
`UNSIGNED_NOT_OFFICIAL`.
