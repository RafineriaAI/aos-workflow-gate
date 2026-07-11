## Gate decision: PASS

**What happened:** Gate PASS: all required checks satisfied; no advisory warnings.
**Signals:** 1 required (1 successful) · 4 advisory (0 warning(s))
**Can block this job:** no
**Next:** set enforce: "true" (or a blocking policy) so a BLOCK verdict fails the job

| Field | Value |
| --- | --- |
| Repository | RafineriaAI/aos-kernel |
| Ref | `refs/heads/main` |
| Commit | `3c00cddf59ebd233cca4761785e20ad51ac9ed78` |
| Policy | `aos-kernel-release-surface` (advisory) |
| Policy digest | `sha256:813550b195c3248805ce605835670dbb59a922af792989ce721e7633be87adcf` |
| Input bundle digest | `sha256:c20cc46731f66437b5cac599e7122ea7dbdc7722f689fff4e171816d31e35a22` |
| Record digest | `sha256:676707c09efbefa33df66d9981a194cad7adac7fea5ca3709558c6056e24e694` |
| Record self-check | OK |
| Verification status | UNSIGNED\_NOT\_OFFICIAL |

### Inputs

| Id | Kind | Required | Status |
| --- | --- | --- | --- |
| ci.validate | github\_check | yes | success |
| codeql.analyze | github\_check | no | success |
| supply-chain.actionlint | github\_check | no | success |
| supply-chain.gitleaks | github\_check | no | success |
| supply-chain.scorecard | github\_check | no | success |

### Coverage

- Required sources: 1 of 5
- Blocking on: `ci.validate`

- Advisory only: a BLOCK verdict would not fail the job (no enforcement configured).
