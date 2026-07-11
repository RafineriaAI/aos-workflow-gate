## Gate decision: WARN

**What happened:** Gate WARN: required checks satisfied; 1 advisory warning(s).
**Signals:** 1 required (1 successful) · 2 advisory (1 warning(s))
**Can block this job:** no
**Next:** advisory findings warn but never block; review the source's own report and decide

| Field | Value |
| --- | --- |
| Repository | owner/repo |
| Ref | `refs/pull/42/merge` |
| Commit | `0123456789abcdef0123456789abcdef01234567` |
| Pull request | #42 |
| Policy | `default` (advisory) |
| Policy digest | `sha256:3f33e4ad37f96d56f5a132d95b4c673aa774d410611111bfef235832aad81272` |
| Input bundle digest | `sha256:dcdfb4bd0853c94bd116dea46e976b90825608a3f07b676ab50144f682dd0a19` |
| Record digest | `sha256:eb2f66cd58e5a519edd12ed62a7a45272defeba93074b12591d19782475e9dcb` |
| Record self-check | OK |
| Verification status | UNSIGNED\_NOT\_OFFICIAL |

### Reasons

- WARN `advisory_warning` scanner.sarif: advisory source status is 'warning'
  - Hint: advisory findings warn but never block; review the source's own report and decide

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
