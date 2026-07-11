## Gate decision: WARN

**What happened:** Gate WARN: required checks satisfied; 1 advisory warning(s).
**Scope:** 1 required and policy-named advisory source(s) on RafineriaAI/aos-workflow-gate@89901ac54cbb; not full merge-readiness
**Freshness:** observation time not recorded; collection complete
**Effect:** advisory — recorded evidence only; a BLOCK verdict does not fail the job
**Signals:** 1 required (1 successful) · 4 advisory (1 warning(s))
**Next:** advisory findings warn but never block; review the source's own report and decide

| Field | Value |
| --- | --- |
| Repository | RafineriaAI/aos-workflow-gate |
| Ref | `refs/pull/32/head` |
| Commit | `89901ac54cbbe74b7dd47491a9ed0ee5bba09f6f` |
| Pull request | #32 |
| Policy | `collected-advisory` (advisory) |
| Policy digest | `sha256:2014a856e0aba1fa1f3b50ffbb1c352d54a75c620b670f81ff7f9f7b7f89c29c` |
| Input bundle digest | `sha256:b6c60a32a3fab0158f40794b5a3d025c3e805d85241e8ab550f9ea05ab509a84` |
| Record digest | `sha256:70621ddd010d0dcf8a4dadb58536eb92c046e21c3a2cc6c341154a028969a313` |
| Record self-check | OK |
| Verification status | UNSIGNED\_NOT\_OFFICIAL |

### Top gaps

- WARN `advisory_warning` AOS Workflow Gate Self / no-checkout: advisory source status is 'skipped'
  - Hint: advisory findings warn but never block; review the source's own report and decide

### Inputs

| Id | Kind | Required | Status |
| --- | --- | --- | --- |
| AOS Workflow Gate CI / validate | github\_check | yes | success |
| AOS Workflow Gate Self / advisory | github\_check | no | success |
| AOS Workflow Gate Self / no-checkout | github\_check | no | skipped |
| AOS Workflow Gate Self / zero-config | github\_check | no | success |
| branch.rules | branch\_rules\_summary | no | success |

### Coverage

- Required sources: 1 of 5
- Blocking on: `AOS Workflow Gate CI / validate`

- Advisory only: a BLOCK verdict would not fail the job (no enforcement configured).
