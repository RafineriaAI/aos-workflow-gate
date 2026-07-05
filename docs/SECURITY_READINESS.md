# Security Readiness

Input-hardening and data-flow reference for security reviewers. This is a
statement of implemented controls with verification steps — not a security
audit, and no security-audit claim is made.

## Private-repo data model

What the gate touches when it runs in your repository, public or private:

| Flow | Content |
| --- | --- |
| Read from the GitHub API (Self-Test Mode only) | Check-run identity metadata for one commit: run id, name, head SHA, status, conclusion, completion timestamp. Never code, diffs, logs, or annotations. |
| Written to the runner workspace | `.aos-gate/` bundle, generated policy, decision record; the Markdown step summary. |
| Sent anywhere else | Nothing. The gate has no telemetry and no server side. |
| Retained by us | Nothing. There is no service; all artifacts stay in your runner and your repository. |

Sharing caveat: a decision record contains check names, statuses, and
summaries. If you upload it as a workflow artifact or commit it, it becomes
visible to whoever can read that location. On private repositories treat
records with the same sensitivity as your check names.

## Implemented input hardening

- **Workspace-bounded safe output paths.** Operator-supplied
  `--out`/`--policy-out` paths are rejected if empty or if they contain
  control characters (newline, carriage return, NUL), and the action
  additionally refuses such an `out` input before anything reaches
  `GITHUB_OUTPUT`. In the action, `AOS_GATE_WORKSPACE` is set to the job
  workspace and every output path must resolve inside it after full
  resolution — traversal (`..`), absolute paths outside the workspace, and
  symlinked escapes are rejected. The action
  therefore writes only within the workspace. Local CLI use without the
  environment variable stays unbounded by design; set `AOS_GATE_WORKSPACE`
  to opt in.
- **Full Markdown escaping.** Every untrusted value rendered into the step
  summary (source ids, kinds, statuses, reason details, subject fields) is
  escaped or forced into a sanitized code span. A fork pull request that
  renames a job to a Markdown payload cannot inject links, images, HTML, or
  table breaks into the summary shown in the base repository.
- **API timeout.** Every check-runs API request carries a 30-second
  timeout; a stalled endpoint fails the step instead of hanging the job.
- **Pagination with fail-closed truncation.** Check runs are collected
  across pages (up to 1000 runs). If the API reports more than were
  collected, a truncation warning is printed and any uncollected required
  check fails closed as missing — truncation can never turn a BLOCK into a
  PASS.
- **API URL validation.** `--api-url` (and `GITHUB_API_URL`) must be a
  well-formed `https` URL without embedded credentials or whitespace.
- **No checkout required.** Self-Test Mode runs without `actions/checkout`,
  so the gate can be used without granting the job a working copy at all;
  the self-test workflow proves this continuously on `main`.

Each control has a negative test in `tests/` — the test suite attacks the
gate with crafted paths, Markdown payloads, and malformed URLs and asserts
rejection.

## Operational resilience

- **Bounded retries.** Transient API failures (timeouts, network errors,
  429, rate-limited 403, 5xx) are retried up to 3 attempts per request
  with capped backoff; `Retry-After` is honored up to 30 seconds. Other
  HTTP errors fail immediately.
- **Hard budgets.** One collection is bounded by a wall-clock deadline
  (default 300 s), a total API-call limit (default 50), and a page limit;
  exhausting any budget is an operational error.
- **Infrastructure failure is never a policy verdict.** Every operational
  failure (retries exhausted, budget exceeded, malformed API response)
  exits with code 2 and produces no decision record — it cannot be
  mistaken for a policy `BLOCK` (exit 1 under enforcement) or for any
  verdict at all.
- **Polling waits only for required checks.** `wait-for-checks` polls
  until the named required checks complete; waiting on "everything" has no
  stop condition because the gate's own job never completes while it
  waits. A wait that ends incomplete is not an error: the missing required
  check fails closed, and the reason is recorded.
- **Collection status is evidence.** The bundle carries a `collection`
  object (status complete/truncated/wait_timeout, API calls used, seconds
  waited, incomplete required checks); the record's `input_bundle_digest`
  anchors it, so operational context is replay-verifiable.
- **`can_block` in the record.** Every decision record states whether the
  evaluation, as configured, could have failed the calling process on
  `BLOCK` — a reader can tell an enforcing gate from an advisory one
  without guessing.

## Permissions posture

`contents: read` plus `checks: read` for Self-Test Mode; no `write` scope
of any kind. See [CI_INTEGRATIONS.md](CI_INTEGRATIONS.md) and
[TRUST.md](TRUST.md) for self-verification steps.

## Known limits

Decision records are `UNSIGNED_NOT_OFFICIAL`; collection reflects GitHub's
reported state and does not make that state tamper-proof; the digest recipe
anchors identity of what was collected, not the correctness of the checks
themselves.
