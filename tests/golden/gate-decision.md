## AOS Workflow Gate: WARN

**What AOS found:** Scanner evidence 'scanner.sarif' contains findings that need review.
**Effect:** advisory only; WARN/BLOCK is reported but does not fail this job
**Next:** review the named SARIF findings for 'scanner.sarif'; promote this source to required only after its signal is stable and useful

**Signals:** 1 required (1 successful); 2 other observation(s)
**Scope:** 1 required check(s) plus recorded workflow signals on owner/repo@0123456789ab; not full merge-readiness
**Freshness:** not recorded (offline or pre-freshness bundle)

### Technical evidence

| Field | Value |
| --- | --- |
| Repository | owner/repo |
| Ref | `refs/pull/42/merge` |
| Commit | `0123456789abcdef0123456789abcdef01234567` |
| Pull request | #42 |
| Policy | `default` (advisory) |
| Policy digest | `sha256:3f33e4ad37f96d56f5a132d95b4c673aa774d410611111bfef235832aad81272` |
| Input bundle digest | `sha256:dcdfb4bd0853c94bd116dea46e976b90825608a3f07b676ab50144f682dd0a19` |
| Record digest | `sha256:d5d835883b8c94bbf345c135dc64f13c434f2e67626e51d780427c48def70090` |
| Record self-check | OK |
| Verification status | UNSIGNED\_NOT\_OFFICIAL |

### Top gaps

- WARN `advisory_warning` scanner.sarif: advisory source status is 'warning'; Advisory findings remain below blocking threshold.
  - Hint: review the named SARIF findings for 'scanner.sarif'; promote this source to required only after its signal is stable and useful

### Inputs

| Id | Kind | Required | Status |
| --- | --- | --- | --- |
| agent.review | ai\_agent\_review\_summary | no | success |
| ci.validate | github\_check | yes | success |
| scanner.sarif | sarif\_summary | no | warning |

### Coverage

- Required sources: 1 of 3
- Blocking on: `ci.validate`

- Advisory only: a BLOCK verdict would not fail the job (no enforcement configured).
