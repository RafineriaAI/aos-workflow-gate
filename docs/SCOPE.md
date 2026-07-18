# Scope

`aos-workflow-gate` is a local-first **pre-merge control assurance** tool. It
verifies how intended CI/CD controls governed one exact commit, applies
explicit policy-as-code, and emits an explainable `PASS`, `WARN`, or `BLOCK`
record. It complements CI, scanners, policy engines, and review; it does not
replace them.

The current release is a free, self-serve advisory preview. Mechanism behavior
is tested and replayable. External usefulness, alert precision, retention,
decision impact, incident reduction, and willingness to pay remain
unvalidated. No active paid product or production recommendation exists.

## Implemented scope

- Local `evaluate` and one-command `run` flows for JSON signal bundles.
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

## Verification status

Outputs use `UNSIGNED_NOT_OFFICIAL`. Their structure, digests, verifier
content address, and replay can be checked; authorship and operator identity
are not cryptographically proven.
