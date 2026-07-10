# Preflight Diagnostics

`aos-workflow-gate preflight` answers one question before anything gates
anything: **what can this token, environment, and target actually do?**
It probes the GitHub API read-only — repository metadata, pull request
access, check runs, commit statuses, and active branch rules — plus the
local runtime and GitHub Actions context, and reports stable diagnostic
codes with remediation.

No permission is assumed without probing: permission models differ
between the workflow `GITHUB_TOKEN`, fine-grained tokens, classic
tokens, and GHES versions, so every capability is classified from the
observed HTTP behavior, never from what a token "should" have.

Preflight produces **no verdict**. It never prints a gate decision and
its report carries no policy outcome — it states which read-only probes
responded, nothing about code quality or security.

## Usage

```bash
# probe a pull request end to end (rules, checks, statuses)
aos-workflow-gate preflight --pr https://github.com/OWNER/REPO/pull/N

# probe a repository (uses the default branch)
aos-workflow-gate preflight --repository OWNER/REPO

# workflow-scoped readiness report: what THIS workflow's token can do
aos-workflow-gate preflight --github-context --json
```

Progressive disclosure: the default view is one summary line plus the
findings; `--verbose` adds one line per probe; `--json` prints the full
machine-readable report (`preflight-report-v0`); `--out PATH` writes it
to a file.

## Exit codes

Preflight has its own exit semantics, documented here and in the
[USER_FAQ exit-code table](USER_FAQ.md#exit-codes-by-command):

| Exit | Meaning |
| --- | --- |
| 0 | Ready — every probed capability responded. |
| 1 | Degraded — at least one probed capability is unavailable; each one is named with a stable code. Not a policy verdict. |
| 2 | The probe run itself could not complete (bad arguments, no target, invalid API URL). |

Probes run in dependency order: when a prerequisite fails (network
unreachable, credentials rejected, repository unavailable), dependent
probes are recorded as `skipped` instead of repeating the same failure.

## Diagnostic code registry

Codes are **stable**: a code never changes meaning across versions. New
codes may be added; existing ones are never repurposed. The taxonomy
prefix states where the problem lives.

### `AOS-ENV-*` — environment

| Code | Severity | Meaning | Remediation direction |
| --- | --- | --- | --- |
| `AOS-ENV-001` | info | No API token available; probing anonymously. | Works for public repositories at a low rate limit; set the token env var to probe your real credentials. |
| `AOS-ENV-002` | error | The API could not be reached (network failure or unexpected response). | Check network egress, proxy configuration, and `--api-url`. |
| `AOS-ENV-003` | error | `AOS_GATE_WORKSPACE` is set but is not an existing directory. | Point it at the job workspace, or unset it for unbounded local paths. |
| `AOS-ENV-004` | warn | Rate-limit window nearly exhausted. | Wait for the reset or authenticate for a higher limit. |

### `AOS-PERM-*` — permission

| Code | Severity | Meaning | Remediation direction |
| --- | --- | --- | --- |
| `AOS-PERM-001` | error | Credentials rejected (HTTP 401). | Replace the invalid, expired, or malformed token. |
| `AOS-PERM-002` | error | Capability forbidden (HTTP 403, not rate-limited). | The finding names the capability and the *likely* cause for common token types — verify against yours; nothing is assumed. |
| `AOS-PERM-003` | error | Resource not found **or hidden** (HTTP 404). | The API reports "does not exist" and "no access" identically; check spelling first, then token repository access. |
| `AOS-PERM-004` | error | Rate limited — capability cannot be determined now. | Wait for the window reset, or authenticate. |

### `AOS-FEAT-*` — feature (capability works, target does not use it)

| Code | Severity | Meaning |
| --- | --- | --- |
| `AOS-FEAT-001` | info | Checks API readable, but zero check runs on the probed commit. |
| `AOS-FEAT-002` | info | No required status checks active on the probed branch — no check outcome is enforced there by rules. |
| `AOS-FEAT-003` | info | No legacy commit statuses on the probed commit (informational). |

### `AOS-CTX-*` — GitHub Actions context

| Code | Severity | Meaning |
| --- | --- | --- |
| `AOS-CTX-001` | error | Actions context incomplete: the identity variables GitHub sets are missing or unusable. |
| `AOS-CTX-002` | info | `--github-context` requested outside a GitHub Actions runtime. |

## Automatic preflight in collection

The same taxonomy fires automatically when a collection request fails:
the *failed response itself* is classified — **no duplicate API call**
is made for the diagnosis — and the operational error carries the
stable code, the named capability, and the remediation, plus explicit
`can_continue` semantics:

- **`can_continue: no`** — an essential stream (check runs, branch
  rules, the pull request itself) failed; the command exits 2 with the
  diagnosis. No verdict is produced.
- **`can_continue: yes`** — a non-essential stream degraded (legacy
  commit statuses in `check-pr`): the command continues, the failure is
  recorded as evidence in the bundle's collection, and any required
  control that only that stream could have satisfied is classified
  `unverifiable` — failing closed, never silently missing.

## Readiness definition

`ready: true` (exit 0) means no `error`-severity finding exists. `info`
and `warn` findings never degrade readiness — they are disclosure, not
failure. The JSON report lists every probe with its observed HTTP
status, so the classification is checkable against the raw evidence.

## Relation to the gate

A degraded preflight predicts the operational errors (exit 2) the gate
would hit mid-collection, and `AOS-FEAT-002` names the adoption gap the
gate exists to close. Preflight itself changes nothing, gates nothing,
and claims nothing beyond the probes' observed responses.
