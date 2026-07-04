# Standards Compatibility

This document defines the intended compatibility surface for industry standards. It is a planning and integration reference, not a compliance claim.

`aos-workflow-gate` should integrate with existing ecosystem formats by consuming, preserving, and referencing their evidence. It should not rebrand a gate decision as a security certification, supply-chain attestation, SBOM, SLSA level, or scanner verdict.

## Current status

Phase 1 implements the local `evaluate` and `verify` CLI with deterministic replay; Phase 2 implements the advisory GitHub Action around the same evaluation. The repository does not yet implement adapters, signed evidence, provenance generation, SBOM export, SARIF upload, or compliance automation.

Any early output remains `UNSIGNED_NOT_OFFICIAL` until signing, publication, and verification controls exist.

## Compatibility principles

- Prefer existing formats over custom workflow evidence whenever a stable ecosystem format exists.
- Preserve source identity, subject identity, digests, timestamps, tool names, and tool versions.
- Normalize only the fields needed for policy evaluation; keep a reference to the original source artifact when possible.
- Treat all external inputs as untrusted until their origin and integrity are explicitly verified.
- Keep scanner, SBOM, provenance, and attestation systems as signal sources, not as hidden authorities.
- Fail closed for malformed mandatory evidence.
- Do not claim compliance with a standard unless the required implementation, tests, release controls, and audit evidence exist.

## Integration map

| Standard or ecosystem format | Intended role | Early boundary |
| --- | --- | --- |
| GitHub Checks and pull request metadata | Input signals for required checks, review state, subject identity, and commit identity. | Read-only collection first; no claim that GitHub state is complete or tamper-proof. |
| SARIF 2.1.0 | Input signal for code scanning summaries, rule ids, severities, locations, and tool identity. | Consume or summarize scanner output; do not present the gate decision itself as a SARIF finding. |
| OpenSSF Scorecard | Advisory supply-chain health signal. | Use as one heuristic input; never as a single final authority. |
| SPDX | Future SBOM presence, license, package, and security metadata signal. | Do not generate or certify SBOMs in early releases. Preserve SBOM identity and digest if supplied. |
| CycloneDX | Future SBOM, VEX, formulation, declaration, or supply-chain metadata signal. | Do not claim CycloneDX conformance until a concrete export or validation path exists. |
| in-toto attestations | Future signed evidence envelope and subject binding model. | Current evidence is unsigned and unofficial; do not call it an attestation. |
| SLSA | Future provenance and verification-summary alignment. | No SLSA level or SLSA compliance claim until build/source requirements and provenance verification are implemented. |
| OPA/Rego or other policy engines | Possible future policy execution backend. | Start with explicit YAML or JSON policies to keep the MVP inspectable. |

## Minimum evidence fields

A standards-aware signal bundle should preserve these fields when available:

- Source id and source type.
- Source URL or artifact reference.
- Subject repository, ref, commit SHA, pull request, or release candidate id.
- Artifact digest or source payload digest.
- Tool name and tool version.
- Native rule, check, package, vulnerability, or attestation identifiers.
- Collection timestamp.
- Policy id and policy digest.
- Verdict and reason emitted by `aos-workflow-gate`.
- Verification status, initially `UNSIGNED_NOT_OFFICIAL`.

## Adoption sequence

1. Local JSON fixture evaluation with deterministic replay.
2. Read-only GitHub Action advisory mode.
3. Minimal adapters for GitHub Checks, PR metadata, SARIF summaries, Scorecard summaries, and dependency update signals.
4. Optional SBOM/provenance presence checks using SPDX, CycloneDX, in-toto, or SLSA-aligned evidence only after the core decision record is stable.
5. Signed decision artifacts and stronger attestation mapping only after release controls and verification tooling exist.

## Market-entry effect

This compatibility surface reduces adoption friction because teams can keep their existing scanners, SBOM tools, CI checks, and policy vocabulary. `aos-workflow-gate` should act as a replayable decision layer over those signals, not as a replacement for them.

For commercial use, the safest public position is interoperability first, certification later. A buyer or auditor should be able to see exactly which standard-shaped inputs were used, which policy consumed them, and why the final gate verdict was produced.

## Source references

These links define the standards and ecosystem surfaces this repository intends to align with over time:

- SLSA specification: https://slsa.dev/spec/v1.2/
- SPDX specifications: https://spdx.dev/use/specifications/
- CycloneDX specification overview: https://cyclonedx.org/specification/overview/
- SARIF support in GitHub code scanning: https://docs.github.com/en/code-security/reference/code-scanning/sarif-files/sarif-support
- OASIS SARIF 2.1.0: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
- in-toto Attestation Framework: https://github.com/in-toto/attestation/blob/main/spec/README.md
- OpenSSF Scorecard: https://github.com/ossf/scorecard
