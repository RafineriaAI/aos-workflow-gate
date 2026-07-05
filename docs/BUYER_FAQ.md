# Buyer FAQ

Short answers for security reviewers and buyers. Where a claim can be
verified independently, [TRUST.md](TRUST.md) shows how.

**What data leaves my environment?**
None through the gate itself. Self-Test Mode calls your own GitHub host's
check-runs API with your own workflow token; everything else runs locally
in your runner. There is no telemetry.

**What permissions does it need?**
`contents: read`, plus `checks: read` for Self-Test Mode. No write scopes.
Explicit-bundle mode needs no API access at all.

**What is free and what is paid?**
The repository, CLI, and GitHub Action are free under Apache-2.0, for
private and commercial use, with no feature gates. The paid offering is the
guided pilot: a scoped engagement where we design the gate policy for one
of your real workflows and hand over measured, replayable results. Request
scoping through the
[guided-pilot form](https://github.com/RafineriaAI/aos-workflow-gate/issues/new?template=guided-pilot-scoping.yml);
submitting it commits neither side.

**What happens if RafineriaAI disappears?**
Your gate keeps working. The code is Apache-2.0, has zero runtime
dependencies, and your decision records verify offline with no service
dependency. There is no server-side component to lose.

**Does PASS mean my repository is secure or compliant?**
No. `PASS` means the explicit policy you chose was satisfied by the signals
you provided. It is not a security audit, a compliance certification, or a
guarantee about the underlying checks.

**Are the records signed?**
No. Records carry `UNSIGNED_NOT_OFFICIAL` status. You can sign exported
in-toto Statements with your own keys today (your claim, not ours). The
**AOS Verdict Seal** designation is reserved for a future officially signed
capability; nothing carries it today.

**Which platforms are supported?**
GitHub.com and GitHub Enterprise Server natively (Self-Test Mode included).
GitLab CI, Jenkins, and any shell run the same platform-neutral core on an
explicitly provided bundle — see [CI_INTEGRATIONS.md](CI_INTEGRATIONS.md).

**How does this relate to EU AI Act / ISO logging standards?**
The record preserves decision factors, input digests, policy identity, and
timestamps — the field families those frameworks care about. We intend to
stay aligned with the emerging logging standards and make no compliance
claim; see [STANDARDS_COMPATIBILITY.md](STANDARDS_COMPATIBILITY.md).

**Who is behind this?**
RafineriaAI (Szymon Hetnar). The workflow gate is the product layer around
the public [aos-kernel](https://github.com/RafineriaAI/aos-kernel)
demonstrator; the private AOS Core technology is separate and not part of
this repository.
