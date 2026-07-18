# Buyer FAQ

Short answers for security reviewers and buyers. Where a claim can be
verified independently, [TRUST.md](TRUST.md) shows how.

**What daily problem does it address?**
AOS verifies the gate, not the code. GitHub spreads merge-control state across
branch rules, check runs, workflow runs, and commit statuses. AOS gives the PR
author or maintainer one exact-commit answer: what required control is missing
or unreliable, whether the result can block, and what to do next. It does not
replace code review.

**Who is the likely user and buyer?**
The daily user is a PR author or maintainer. The likely buyer, if a paid
offering is later justified, is a platform, DevOps, DevSecOps, or engineering
governance owner responsible for consistent controls across repositories.

**What business value is currently proven?**
Only the mechanism: deterministic evaluation, exact-commit binding,
tamper detection, and offline reproduction. Reduced review time, fewer
incidents, audit savings, retention, and willingness to pay remain product
hypotheses to measure during free advisory validation.


**What data leaves my environment?**
None through the gate itself. Self-Test Mode makes read-only calls to
your configured GitHub host for repository, PR, checks, Actions, rules,
and statuses data using your workflow token. There is no telemetry.

**What permissions does it need?**
`contents: read`, `checks: read`, `actions: read`, `pull-requests: read`, and `statuses: read` for Self-Test Mode. No write scopes.
Explicit-bundle mode needs no API access at all.

**What is free and what is paid?**
The repository, CLI, and GitHub Action are free under Apache-2.0, for
private and commercial use, with no feature gates. There is currently no
active paid offering. Free self-serve advisory validation is open; guided
onboarding and paid pilot intake remain closed while the
[Hybrid Value Gate](../benchmarks/value/ASSESSMENT.md) is `NO_GO`.
The future pilot specification describes policy design and replayable
handover, but it is not an offer and has no active intake path.

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
The record can preserve decision factors, input digests, policy identity, and
timestamps when supplied. That may support an operator's own recordkeeping,
but AOS makes no EU AI Act, ISO, audit, or compliance claim. See
[STANDARDS_COMPATIBILITY.md](STANDARDS_COMPATIBILITY.md).

**Who is behind this?**
RafineriaAI (Szymon Hetnar). The gate shares the verdict vocabulary and design
lineage of the public
[aos-kernel](https://github.com/RafineriaAI/aos-kernel), but the Python package
is standalone and has no runtime kernel dependency. Private AOS Core
technology is separate and not part of this repository.
