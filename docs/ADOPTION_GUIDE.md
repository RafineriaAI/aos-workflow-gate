# Adoption Guide

This guide is written for developers who understand CI and pull requests but may not know formal methods, supply-chain standards, or the AOS project structure.

## One-sentence model

`aos-workflow-gate` turns many workflow signals into one explicit, replayable gate decision.

## Competency unblock

You do not need to understand Lean, formal verification, SLSA, in-toto, OPA, or the internal implementation of `aos-kernel` to understand the first useful product shape.

You only need these concepts:

- Signal: a piece of workflow evidence, such as a CI check result or scanner summary.
- Policy: the explicit rule set that says which signals matter.
- Verdict: `PASS`, `WARN`, or `BLOCK`.
- Evidence record: the JSON artifact that explains what input and policy produced the verdict.
- Verification status: whether the output is signed or official. Early outputs stay `UNSIGNED_NOT_OFFICIAL`.

## What you can do now

- Read [docs/SCOPE.md](SCOPE.md) before assuming what the project claims.
- Inspect [examples/github-pr-signal-bundle.json](../examples/github-pr-signal-bundle.json) to see the intended input shape.
- Inspect [policies/default.yml](../policies/default.yml) to see the initial advisory policy shape.
- Run python tools/check_public_surface.py to verify that the bootstrap docs and examples still match the claim boundary.

## Adoption ladder

1. Read-only local fixture evaluation.
2. Advisory GitHub Action comment or summary.
3. Required status check after repeated stable behavior.
4. Stronger provenance, signing, and attestation only after the decision record is mature.

## Barriers and design responses

| Barrier | Design response |
| --- | --- |
| The project sounds abstract. | Start with a PR gate use case and concrete `PASS/WARN/BLOCK` output. |
| The user does not know formal methods. | Keep Lean and kernel semantics behind a small verdict contract. |
| Teams fear unexpected blocking. | Start in advisory mode and require explicit policy promotion to blocking mode. |
| Security terms create overclaim risk. | State that a gate verdict is not a security or compliance certification. |
| CI integrations are risky. | Use read-only permissions first and treat external input as untrusted. |
| Audit reviewers need traceability. | Preserve subject, policy, source ids, digests, verdict, and verification status. |

## Documentation approach

This repository follows a task-first documentation structure:

- README: what it is, why it matters, and where to go next.
- Use cases: concrete workflows.
- Scope: claim boundaries.
- Architecture: system explanation.
- Roadmap: release sequencing.

This follows the same separation of user needs used by the Diataxis documentation framework: tutorials, how-to guides, reference, and explanation.

## Research inputs

The initial adoption surface is based on:

- GitHub README guidance: a repository should explain what the project does, why it is useful, how to get started, and where to get help.
- Diataxis: documentation should be organized around user needs, not just implementation structure.
- Nielsen Norman Group usability heuristics: minimize memory load, use language users understand, and provide concise task-focused help.
- GitHub Actions security guidance: use least privilege and be careful with third-party actions and untrusted input.
- OpenSSF Scorecard: use ecosystem security signals as inputs, not as a single final authority.

Source links are intentionally kept in this guide so future reviewers can inspect the rationale:

- https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes
- https://diataxis.fr/
- https://www.nngroup.com/articles/ten-usability-heuristics/
- https://docs.github.com/en/actions/reference/security/secure-use
- https://github.com/ossf/scorecard
