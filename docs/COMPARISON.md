# Comparison: Pre-Merge Control Assurance and Adjacent Layers

A capability matrix, **not a ranking**: different tools answer different
questions. AOS is designed to consume their results as signals rather than
replace them. Every cell describes documented behavior with a source link; no
competitor tool was benchmarked or scored here, and no superiority is claimed.


## Product role

AOS is designed as an add-on to existing test runners, coverage services,
scanners, and repository rules. `aos-check` reduces first-run friction but is
not the primary differentiation experiment. `prove-change` adds one bounded
question to an existing targeted test command: would that command still pass
if the actual PR implementation patch were absent?

Unlike an AI reviewer, AOS does not infer intent or use an LLM. Unlike a hosted
test service, it does not upload source code to RafineriaAI. The claim is a
differentiated integration pattern, not a unique market category or a proven
moat.

## Category boundary

- **AI reviewers and scanners** inspect code or artifacts for defects and
  findings.
- **Branch protection and rulesets** decide whether registered platform
  requirements permit merge.
- **OPA and conftest-style engines** evaluate general policy over supplied
  structured inputs.
- **in-toto and SLSA tooling** represent or verify supply-chain attestations.
- **AOS** performs pre-merge control assurance: it records whether intended
  controls governed one exact commit, under an explicit policy, with a
  replayable decision.

The positioning is deliberately narrow. `PASS/WARN/BLOCK`, policy-as-code,
and evidence records are not individually unique.

## Questions at gate time

| Question | Branch protection / rulesets | OPA / conftest | in-toto attestations | aos-workflow-gate |
| --- | --- | --- | --- | --- |
| Primary job | Enforce registered repository requirements | Evaluate general policy over supplied data | Bind a signed predicate to an artifact | Verify and record exact-commit control execution |
| Decision output | Platform merge state and check UI ([docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)) | Exit code and console output per policy test ([docs](https://www.conftest.dev/)) | Signed statement ([spec](https://github.com/in-toto/attestation/blob/main/spec/README.md)) | Canonical decision record with subject, policy, reasons, and digests |
| Offline replay | No portable AOS-style decision record | Requires the same policy and inputs to be retained | Signature and predicate verification | `verify` and semantic replay with committed artifacts |
| Missing versus passed | Required checks block when missing; non-required absence is not a policy gap | Only when modeled by the policy author | Absence is detectable by a verifier | Built-in required-source and collection-completeness semantics |
| Expected producer identity | GitHub supports app-bound required checks | Only when modeled in inputs and policy | Signer identity is part of attestation verification | App-bound control identity is retained in the decision evidence |
| Verifier changed by the same PR | Not a built-in branch-rule decision | Possible when modeled | Outside generic statement verification | Built-in deterministic advisory signal |
| Signing authority | Platform-internal state | No signing model of its own | Core capability | None; `UNSIGNED_NOT_OFFICIAL`, with operator-key export |

## Differentiating bundle

AOS combines:

1. exact repository and head-SHA observation scope;
2. control identity separated from requirement provenance;
3. fail-closed missing, stale, incomplete, and unverifiable evidence;
4. verifier-change independence detection;
5. canonical policy, verifier manifest, record digest, and offline replay;
6. a local-first, read-only default gate without source-code upload or
   telemetry.

The combination is the product hypothesis, not a proven moat. Durable
commercial differentiation would require low-noise real-world policies, a
corpus of independently adjudicated control failures, evidence
interoperability, and organization-level operations that users retain.

## Experimental change-sensitivity comparison

| Existing layer | What it establishes | What Change Proof adds | Remaining gap |
| --- | --- | --- | --- |
| [GitHub required checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks) | A named result reached an accepted state for the relevant commit | Re-runs an explicit verifier against the actual patch counterfactual | Does not prove intended behavior or defect absence |
| [Codecov patch coverage](https://docs.codecov.com/docs/frequently-asked-questions) | Changed lines were executed by tests | Checks whether the verifier outcome changes when the implementation patch is removed | Execution and outcome sensitivity still do not prove correct assertions |
| [Stryker](https://stryker-mutator.io/docs/stryker-js/incremental/) or [PIT](https://pitest.org/quickstart/incremental_analysis/) | Tests kill many small synthetic mutants, with language-specific analysis | One coarse counterfactual aligned with the submitted Git diff and any argv-based verifier | Mutation testing is finer-grained and has stronger established evidence |
| [SonarQube PR analysis](https://docs.sonarsource.com/sonarqube-server/2026.1/analyzing-source-code/pull-request-analysis/introduction) | Static issues and quality-gate measures on new code | Dynamic sensitivity of the team's own verifier | Neither reconstructs business intent |
| AI reviewer | Probabilistic review of code and context | Deterministic, replayable execution with no LLM verdict | AOS does not find semantic defects outside the supplied verifier |

Mutation testing is the closest established category.
[Google's large-scale study](https://research.google/pubs/practical-mutation-testing-at-scale-a-view-from-google/)
reports incremental, context-filtered mutation testing in code review by more
than 24,000 developers across more than 1,000 projects. Stryker and PIT both
provide incremental modes. AOS is coarser but potentially easier to add across
languages because it consumes a Git diff and an existing command; that setup
advantage is not yet measured.

A non-exhaustive GitHub and Marketplace search on 2026-08-01 did not surface a
mature Action with this exact combination: actual-patch counterfactual, any
argv-based verifier, exact-SHA evidence, and offline replay. That is discovery
evidence, not proof of an empty category. Language-agnostic mutation tools such
as [UniversalMutator](https://github.com/agroce/universalmutator) and
[MutaHunter](https://github.com/codeintegrity-ai/mutahunter) already address
test adequacy, and agent-focused mutation gates are emerging. AOS must win on
setup time, accepted findings, low noise, and runtime cost rather than claim
market exclusivity.

The committed eight-case experiment shows mechanism behavior and the need for
eligibility calibration. It does not benchmark competitor precision or prove
superiority. See the
[Change Proof report](../benchmarks/change-proof-plugin/REPORT.md).

## Complementary by design

Branch protection defines requirements, policy engines and scanners can supply
signals, and AOS records the bounded decision. AOS records can also export as
unsigned in-toto Statements for operator-key signing. Use in-toto/SLSA tooling
for signed build provenance and conftest/OPA for general policy expressiveness;
AOS does not claim to replace either.

## Boundary

Cells describe documented behavior as of 2026-08-01 with sources linked. Tools
evolve, and corrections are welcome. This document makes no superiority,
security, compliance, market-demand, or ROI claim.
