## Gate decision: PASS

**What happened:** Gate PASS: all required checks satisfied; no advisory warnings.
**Signals:** 1 required (1 successful) · 2 advisory (0 warning(s))
**Can block this job:** no
**Next:** set enforce: "true" (or a blocking policy) so a BLOCK verdict fails the job

| Field | Value |
| --- | --- |
| Repository | RafineriaAI/aos-workflow-gate |
| Ref | `refs/pull/23/merge` |
| Commit | `3f166868021884ab42f80fd4e018623a8755d610` |
| Pull request | #23 |
| Policy | `collected-advisory` (advisory) |
| Policy digest | `sha256:91b6374ac5cbff06c473af050fac34929b1c20bf19ba1d6a64e1c05de96c8fad` |
| Input bundle digest | `sha256:a06a19c633c11a343a622b96fa201ddcbd1b88176565ac93e6ee2fd7c29a973d` |
| Record digest | `sha256:70f97062702f4e3e57b5f152dac9d68852a3cb6cb964a16ce79baabc86d3122e` |
| Record self-check | OK |
| Verification status | UNSIGNED\_NOT\_OFFICIAL |

### Inputs

| Id | Kind | Required | Status |
| --- | --- | --- | --- |
| AOS Workflow Gate CI / validate | github\_check | yes | success |
| AOS Workflow Gate Self / advisory | github\_check | no | success |
| AOS Workflow Gate Self / zero-config | github\_check | no | success |

### Coverage

- Required sources: 1 of 3
- Blocking on: `AOS Workflow Gate CI / validate`

- Advisory only: a BLOCK verdict would not fail the job (no enforcement configured).
