## Gate decision: WARN

**What happened:** Gate WARN: the policy requires nothing, so nothing can block; 4 warning(s).
**Signals:** 0 required (0 successful) · 4 advisory (4 warning(s))
**Can block this job:** no
**Next:** nothing is required, so nothing can block; name required checks (see the suggestion under Coverage) to close the decision gap

| Field | Value |
| --- | --- |
| Repository | RafineriaAI/aos-workflow-gate |
| Commit | `f8c6517bef32e68d3150d2954cc4c445b6fb1642` |
| Policy | `collected-advisory` (advisory) |
| Policy digest | `sha256:1ac10c8a010a4e3a9f62894184bfd9ba342626922ac4f6dd987f8ca6f0a06cb0` |
| Input bundle digest | `sha256:c201708d94aaa4c59e6473ee12cfceb93842f78e443a3350951c96bd96ee8837` |
| Record digest | `sha256:3b7a8f035d0b622f199c6c4533e1f0465fbdbaf78319ddd25d5699a7a65982ec` |
| Record self-check | OK |
| Verification status | UNSIGNED\_NOT\_OFFICIAL |

### Reasons

- WARN `no_required_sources` -: the policy requires nothing, so no missing or failed check can make this gate BLOCK — the record is evidence, not enforcement
  - Hint: nothing is required, so nothing can block; name required checks (see the suggestion under Coverage) to close the decision gap
- WARN `advisory_warning` AOS Workflow Gate Self / advisory: advisory source status is 'failure'
  - Hint: advisory findings warn but never block; review the source's own report and decide
- WARN `advisory_warning` AOS Workflow Gate Self / no-checkout: advisory source status is 'skipped'
  - Hint: advisory findings warn but never block; review the source's own report and decide
- WARN `advisory_warning` AOS Workflow Gate Self / zero-config: advisory source status is 'failure'
  - Hint: advisory findings warn but never block; review the source's own report and decide

### Inputs

| Id | Kind | Required | Status |
| --- | --- | --- | --- |
| AOS Workflow Gate CI / validate | github\_check | no | success |
| AOS Workflow Gate Self / advisory | github\_check | no | failure |
| AOS Workflow Gate Self / no-checkout | github\_check | no | skipped |
| AOS Workflow Gate Self / zero-config | github\_check | no | failure |

### Coverage

- Required sources: 0 of 4
- Decision gap: no source is required, so a missing or failed check cannot make this gate BLOCK. The record is evidence, not enforcement.
- Suggestion: start with your detected checks, then trim: `required-checks: "AOS Workflow Gate CI / validate, AOS Workflow Gate Self / advisory, AOS Workflow Gate Self / no-checkout, AOS Workflow Gate Self / zero-config"`
