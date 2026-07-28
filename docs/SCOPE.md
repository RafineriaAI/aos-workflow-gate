# Scope

`aos-workflow-gate` contains two bounded product surfaces. The released GitHub
Action is a local-first **pre-merge control assurance** tool. The `0.38.0`
candidate adds `aos-check`, a beginner-facing local code-verification entry
point that runs conventional project checks without Git or manual
configuration. Both emit explainable `PASS`, `WARN`, or `BLOCK` records and
reuse the same deterministic evidence pipeline. Neither proves general code
or business correctness.

The current release is a free, self-serve advisory preview. Mechanism behavior
is tested and replayable. External usefulness, alert precision, retention,
decision impact, incident reduction, and willingness to pay remain
unvalidated. No active paid product or production recommendation exists.

The candidate `aos-check` surface detects Python, Node.js, Go, Rust, Maven, and
Gradle root projects, runs only their conventional existing checks, and names
a missing behavioral test rather than returning a misleading `PASS`. It does
not yet explore a running application, generate adversarial tests, or verify a
plain-language product requirement.


The opt-in experimental `prove-change` surface performs one bounded code
experiment outside the default Action: it tests whether an operator-supplied
verifier distinguishes the exact head implementation from the merge-base
implementation. It does not change the released control-assurance claim.

## Implemented scope

- Local `evaluate` and one-command `run` flows for JSON signal bundles.
- Candidate local `aos-check` / `check-project` without a Git requirement,
  dependency installation, shell invocation, code upload, or telemetry.
- Experimental local `prove-change` with disposable Git worktrees,
  two-run confirmation, exact-SHA evidence, and no LLM verdict.
- Zero-config GitHub Action collection for the exact head SHA.
- Active ruleset and classic branch-protection requirement discovery.
- Check Run, Check Suite, Workflow Run, and commit-status visibility.
- App-bound control identity, requirement provenance, freshness, collection
  completeness, and fail-closed evidence states.
- Versioned `source-v0` and `agent-action-v0` validation.
- SARIF 2.1.0 and OpenSSF Scorecard file adapters.
- Explicit JSON or restricted-YAML policy and packaged starter policies.
- Deterministic Markdown and static HTML diagnosis with one dominant next
  action.
- Canonical digests, verifier manifest, tamper detection, offline replay, and
  unsigned in-toto Statement export.
- Read-only preflight diagnostics and committed benchmark verification.

External adapters may supply CI, pull-request, scanner, dependency, or agent
observations through `source-v0`. Their presence is not a claim that AOS
independently verifies the originating system.

## Out of scope

- Full merge-readiness: reviews, conversations, merge queue state, conflicts,
  deployment safety, business correctness, and every GitHub merge rule.
- Defect absence, vulnerability absence, or repository security.
- Compliance or security-audit certification.
- Runtime proof that GitHub, CI, a scanner, or an agent reported truthfully.
- Official RafineriaAI signing, hosted provenance, SBOM generation, SLSA level,
  or attestation service.
- Workflow orchestration, dashboarding, automatic remediation, or code
  generation.
- LLM-based verdicts.
- A production recommendation or efficacy claim before external validation.

## Decision boundary

A gate decision means only:

> For the stated subject, policy, input bundle, and verifier artifact, the gate
> produced this verdict and replayable record.

For `prove-change`, `PASS` means the explicit verifier passed at `HEAD` and

For `aos-check`, `PASS` means every discovered project check passed and at
least one behavioral test ran. `WARN` means a behavioral test or another
verification prerequisite was unavailable. `BLOCK` means a discovered check
failed. These states cover only discovered local commands, not every user
flow, requirement, edge case, or vulnerability.

failed twice after the selected implementation patch was removed. `WARN` means
the checks did not distinguish the change or the experiment was inconclusive.
`BLOCK` means the explicit verifier failed twice at `HEAD`. None of these
states proves business correctness or defect absence.

It does not mean the underlying source signals are complete, honest, or
independently verified unless the record contains evidence for that property.
`PASS` means every requirement declared by the evaluated policy was
satisfied; residual unknown risk remains.

A verdict and a process exit code are distinct. The verdict states policy
readiness. Advisory or enforce mode determines whether a `BLOCK` interrupts
the calling process.

## Kernel relationship

The package shares the public verdict vocabulary and design lineage of
`aos-kernel`, but the current Python implementation has no runtime dependency
on the kernel and makes no formal-proof claim. Workflow semantics, contracts,
digests, and integration behavior are owned and tested in this repository.
No artifact produced here is kernel-generated or kernel-verified. A future
kernel-backed claim requires a versioned shared contract and conformance
vectors executed in both repositories.

## Verification status

Outputs use `UNSIGNED_NOT_OFFICIAL`. Their structure, digests, verifier
content address, and replay can be checked; authorship and operator identity
are not cryptographically proven.
