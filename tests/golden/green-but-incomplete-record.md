## Gate decision: WARN

**What happened:** Gate WARN: required checks satisfied; 1 advisory warning(s).
**Signals:** 1 required (1 successful) · 3 advisory (1 warning(s))
**Can block this job:** no
**Next:** advisory findings warn but never block; review the source's own report and decide

| Field | Value |
| --- | --- |
| Repository | RafineriaAI/aos-workflow-gate |
| Ref | `refs/pull/22/merge` |
| Commit | `9c064fc8c95d21453d553dc81e9a935ccfa54630` |
| Pull request | #22 |
| Policy | `collected-advisory` (advisory) |
| Policy digest | `sha256:307c1f8738f94d966f3911f67d927ac749182aa544390fa8928105ddbc8d6237` |
| Input bundle digest | `sha256:54949f798a0dbd4e64765c515b0ae828dbc61fb6ed4c9ceb66e174ecc61bfc7f` |
| Record digest | `sha256:8cf2ef04aaf9c58ce3a7f55acb92b171da9ac23a0c08c3ca025ff4dbd7242e68` |
| Record self-check | OK |
| Verification status | UNSIGNED\_NOT\_OFFICIAL |

### Reasons

- WARN `advisory_warning` AOS Workflow Gate Self / no-checkout: advisory source status is 'skipped'
  - Hint: advisory findings warn but never block; review the source's own report and decide

### Inputs

| Id | Kind | Required | Status |
| --- | --- | --- | --- |
| AOS Workflow Gate CI / validate | github\_check | yes | success |
| AOS Workflow Gate Self / advisory | github\_check | no | success |
| AOS Workflow Gate Self / no-checkout | github\_check | no | skipped |
| AOS Workflow Gate Self / zero-config | github\_check | no | success |

### Coverage

- Required sources: 1 of 4
- Blocking on: `AOS Workflow Gate CI / validate`

- Advisory only: a BLOCK verdict would not fail the job (no enforcement configured).
