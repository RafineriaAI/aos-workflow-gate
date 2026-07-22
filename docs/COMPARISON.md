# Comparison: Pre-Merge Control Assurance and Adjacent Layers

A capability matrix, **not a ranking**: different tools answer different
questions. AOS is designed to consume their results as signals rather than
replace them. Every cell describes documented behavior with a source link; no
competitor tool was benchmarked or scored here, and no superiority is claimed.


## Local product candidate

`aos-check` is a convenience and decision layer over conventional local
project checks. Unlike an AI reviewer, it does not infer defects from source
text. Unlike a hosted browser-testing agent, it does not yet explore user
flows. Unlike a test runner, it detects the project, selects supported
surfaces, distinguishes failed from missing verification, and produces one
plain-language next action plus a replayable local record.

That combination lowers first-run friction but is not yet a demonstrated moat.
AOS becomes materially differentiated only when its adversarial or runtime
verification produces accepted findings that ordinary build/test and existing
review tools miss at acceptable runtime and noise. Until measured, the local
surface is a product experiment rather than a superiority claim.

See [Local Project Check](PROJECT_CHECK.md) for the exact implemented boundary.

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

Ordinary CI runs the repository checks on `HEAD`; it does not normally ask
whether those checks would still pass if the PR implementation were absent.
Mutation testing tools introduce many small synthetic code changes and report
whether tests kill or survive each mutant
([Stryker semantics](https://stryker-mutator.io/docs/mutation-testing-elements/mutant-states-and-metrics/)).

Experimental `prove-change` removes the selected PR implementation patch as
one coarse counterfactual and runs the operator's verifier in clean worktrees.
Its hypothesized advantages are direct alignment with the submitted change,
few verifier runs, language-independent command execution, and reuse of
exact-SHA decision evidence. Its disadvantages are equally material: it is
coarser than mutation testing, can fail structurally rather than behaviorally,
does not generate boundary cases, and may require environment adaptation.

This is not a superiority claim. A valid product comparison must measure
accepted incremental findings, inconclusive rate, runtime cost, and remediation
beyond ordinary CI and the repository's established mutation tooling.

## Complementary by design

Branch protection defines requirements, policy engines and scanners can supply
signals, and AOS records the bounded decision. AOS records can also export as
unsigned in-toto Statements for operator-key signing. Use in-toto/SLSA tooling
for signed build provenance and conftest/OPA for general policy expressiveness;
AOS does not claim to replace either.

## Boundary

Cells describe documented behavior as of 2026-07-18 with sources linked. Tools
evolve, and corrections are welcome. This document makes no superiority,
security, compliance, market-demand, or ROI claim.
