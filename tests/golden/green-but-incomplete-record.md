## AOS Workflow Gate: WARN

**What AOS found:** Non-required check 'AOS Workflow Gate Self / no-checkout' ended as 'skipped'.
**Effect:** advisory only; WARN/BLOCK is reported but does not fail this job
**Next:** review the named non-required check only if it matters to this change; it cannot block this gate

**Signals:** 1 required (1 successful); 3 other observation(s)
**Scope:** 1 required check(s) plus recorded workflow signals on RafineriaAI/aos-workflow-gate@9c064fc8c95d; not full merge-readiness
**Freshness:** observation time not recorded; collection complete

### Technical evidence

| Field | Value |
| --- | --- |
| Repository | RafineriaAI/aos-workflow-gate |
| Ref | `refs/pull/22/merge` |
| Commit | `9c064fc8c95d21453d553dc81e9a935ccfa54630` |
| Pull request | #22 |
| Policy | `collected-advisory` (advisory) |
| Policy digest | `sha256:307c1f8738f94d966f3911f67d927ac749182aa544390fa8928105ddbc8d6237` |
| Input bundle digest | `sha256:54949f798a0dbd4e64765c515b0ae828dbc61fb6ed4c9ceb66e174ecc61bfc7f` |
| Record digest | `sha256:b5db48077d143b4feb2fedff2a3419be5f9570b1a2654221d0f5f63a2db34015` |
| Record self-check | OK |
| Verification status | UNSIGNED\_NOT\_OFFICIAL |

### Top gaps

- WARN `advisory_warning` AOS Workflow Gate Self / no-checkout: advisory source status is 'skipped'
  - Hint: review the named non-required check only if it matters to this change; it cannot block this gate

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
