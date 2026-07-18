## AOS Workflow Gate: WARN

**What AOS found:** This policy requires no checks, so no check result can block the gate.
**Effect:** advisory only; WARN/BLOCK is reported but does not fail this job
**Next:** configure at least one required status check in GitHub, or pass required-checks explicitly, then re-run AOS

**Signals:** 0 required (0 successful); 4 other observation(s)
**Scope:** 0 required check(s) plus recorded workflow signals on RafineriaAI/aos-workflow-gate@f8c6517bef32; not full merge-readiness
**Freshness:** observation time not recorded; collection complete

### Technical evidence

| Field | Value |
| --- | --- |
| Repository | RafineriaAI/aos-workflow-gate |
| Commit | `f8c6517bef32e68d3150d2954cc4c445b6fb1642` |
| Policy | `collected-advisory` (advisory) |
| Policy digest | `sha256:92018eb3494bb955e306ceaedb8bf6f7f26a9e980fee670b43fd2dc1b8b0c7fa` |
| Input bundle digest | `sha256:c201708d94aaa4c59e6473ee12cfceb93842f78e443a3350951c96bd96ee8837` |
| Record digest | `sha256:6b394e153223f27175301f788c41963867ba4a5b19a2678e0d7b704a788c9129` |
| Record self-check | OK |
| Verification status | UNSIGNED\_NOT\_OFFICIAL |

### Top gaps

- WARN `no_required_sources` -: the policy requires nothing, so no missing or failed check can make this gate BLOCK - the record is evidence, not enforcement
  - Hint: configure at least one required status check in GitHub, or pass required-checks explicitly, then re-run AOS

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
