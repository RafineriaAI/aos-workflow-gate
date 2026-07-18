# Buyer FAQ

Short answers for maintainers, platform and DevSecOps owners, security
reviewers, and potential buyers. Where a claim can be verified independently,
[TRUST.md](TRUST.md) shows how.

**What operational problem does it address?**
AOS verifies the gate, not the code. A green PR can still rely on a control
that is missing, stale, produced by the wrong app, or modified by the same PR.
AOS gives the
maintainer one exact-commit answer: which intended control is missing or
unreliable, whether AOS found something beyond GitHub's own block, and what to
do next.

**Who is the user and who could become the buyer?**
The primary operator is a maintainer, platform engineer, or DevSecOps owner.
Security and assurance reviewers consume the retained evidence. If a paid
offering is justified later, the likely buyer is the owner of consistent
software-delivery controls across repositories. An individual developer is a
weak paid ICP; the free CLI may still provide occasional pre-review value.

**Is this another AI reviewer or scanner?**
No. AOS does not inspect code for defects, generate review comments, or infer
AI authorship. Reviewers and scanners produce findings. AOS verifies whether
the intended controls actually governed the exact commit and preserves that
decision.

**Is it a wrapper around CI or a general policy engine?**
Not if used for its intended scope. A thin wrapper would only restate statuses.
AOS additionally binds observations to the exact subject, preserves app-bound
control identity and requirement provenance, detects a verifier changed by the
same PR, fails closed on incomplete collection, and produces a canonical
record for offline replay. It remains narrower than a general policy engine.

**What business value is currently proven?**
Only mechanism behavior: deterministic evaluation, exact-commit binding,
tamper detection, and offline reproduction. Reduced review or investigation
time, fewer incidents, audit savings, alert precision, retention, and
willingness to pay remain hypotheses to measure during free advisory
validation.

**Why can a low-frequency signal still matter?**
A control-plane failure may be rare but expensive to reconstruct after merge.
The commercial hypothesis is lower uncertainty, faster remediation, and
portable assurance evidence - not a high volume of alerts. That hypothesis is
not yet externally validated.

**What would a future customer pay for if the Action stays free?**
Potential organization-level jobs include cross-repository control inventory
and drift, exception and override governance, durable evidence retention and
export, assurance reporting, and possibly managed signing. Policy packs alone
are too copyable to be the primary paid moat. There is no active paid offering.

**What data leaves my environment?**
None through the gate itself. Self-Test Mode makes read-only calls to your
configured GitHub host for repository, PR, checks, Actions, rules, and statuses
data using your workflow token. There is no telemetry.

**What permissions does it need?**
`contents: read`, `checks: read`, `actions: read`, `pull-requests: read`, and
`statuses: read` for Self-Test Mode. No write scopes. Explicit-bundle mode
needs no API access at all.

**What is free and what is paid?**
The repository, CLI, and GitHub Action are free under Apache-2.0 for private
and commercial use, with no feature gates. There is currently no active paid
offering. Free self-serve advisory validation is open; guided onboarding and
paid pilot intake remain closed while the
[Hybrid Value Gate](../benchmarks/value/ASSESSMENT.md) is `NO_GO`.

**What happens if RafineriaAI disappears?**
The local gate keeps working. The code is Apache-2.0, has zero runtime
dependencies, and decision records verify offline with no service dependency.
There is no server-side component to lose.

**Does PASS mean my repository is secure or compliant?**
No. `PASS` means the explicit policy was satisfied by the supplied and
collected signals. It is not a security audit, compliance certification, or
guarantee about the underlying controls.

**Are the records signed?**
No. Records carry `UNSIGNED_NOT_OFFICIAL` status. Operators can sign exported
in-toto Statements with their own keys today. The **AOS Verdict Seal**
designation is reserved for a future officially signed capability; nothing
carries it today.

**Which platforms are supported?**
GitHub.com and GitHub Enterprise Server are native collection surfaces.
GitLab CI, Jenkins, and any shell can run the platform-neutral core with an
explicit bundle; see [CI_INTEGRATIONS.md](CI_INTEGRATIONS.md).

**How does this relate to EU AI Act or ISO logging standards?**
The record can preserve decision factors, input digests, policy identity, and
timestamps when supplied. That may support an operator's recordkeeping, but
AOS makes no EU AI Act, ISO, audit, or compliance claim. See
[STANDARDS_COMPATIBILITY.md](STANDARDS_COMPATIBILITY.md).

**Who is behind this?**
RafineriaAI (Szymon Hetnar). The gate shares verdict vocabulary and design
lineage with the public
[aos-kernel](https://github.com/RafineriaAI/aos-kernel), but the Python package
is standalone. Private AOS Core technology is separate and not included.
