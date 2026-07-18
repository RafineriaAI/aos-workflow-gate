# Standards Compatibility

This is an interoperability reference, not a compliance claim.
`aos-workflow-gate` consumes or preserves ecosystem-shaped evidence without
rebranding a decision record as a scanner result, security certification,
SBOM, provenance statement, SLSA level, or signed attestation.

## Current status

Implemented:

- read-only GitHub rules, Checks, Check Suites, Workflow Runs, pull-request
  metadata, and commit-status collection;
- SARIF 2.1.0 file reduction with a fixed documented status mapping;
- OpenSSF Scorecard presence-and-integrity input;
- canonical source, subject, policy, record, and verifier digests;
- unsigned in-toto Statement v1 export containing the verified decision record.

Not implemented: RafineriaAI signing, provenance generation, SBOM generation,
SARIF upload, SLSA conformance, SPDX or CycloneDX validation, OPA/Rego
execution, or compliance automation. Outputs remain
`UNSIGNED_NOT_OFFICIAL`.

## Compatibility principles

- Prefer a stable ecosystem format when one exists.
- Preserve source and subject identity, native identifiers, digests,
  timestamps, tool names, and tool versions when available.
- Normalize only decision-relevant observations and retain an artifact
  reference where possible.
- Keep adapter status separate from policy verdict.
- Treat external inputs as untrusted; a file format does not prove origin or
  correctness.
- Fail closed for malformed mandatory evidence.
- Do not claim conformance without the implementation, conformance tests,
  release controls, and auditable evidence required by that standard.

## Integration map

| Standard or ecosystem | Current role | Boundary |
| --- | --- | --- |
| GitHub rules, Checks, Actions, and Statuses | Built-in exact-SHA requirement and observation source. | Read-only metadata collection; not full merge-readiness and not proof GitHub is truthful or complete. |
| SARIF 2.1.0 | `collect --sarif` maps result levels to one mechanical `source-v0` status. | No SARIF upload, authenticity check, or scanner reinterpretation. |
| OpenSSF Scorecard | `collect --scorecard` preserves presence, score data, and source digest. | A score is data, never a hidden gate authority. |
| `source-v0` | Versioned extension contract for external evidence. | No plugin runtime; the source cannot mark itself required. |
| in-toto Statement v1 | `export` wraps a verified record and binds the gated commit digest. | Unsigned projection; it must not be called an attestation until signed. |
| SPDX | Possible future SBOM evidence input. | No current parser, generator, validation, or certification. |
| CycloneDX | Possible future SBOM, VEX, or formulation evidence input. | No current parser, generator, validation, or conformance claim. |
| SLSA | Possible future provenance or verification-summary mapping. | No current level, provenance, or compliance claim. |
| OPA/Rego | Possible future policy backend. | Current policy is explicit JSON or restricted YAML; no Rego execution. |

## Minimum evidence fields

When available, a standards-shaped source should preserve:

- source ID, type, URL or artifact reference;
- repository, ref, exact commit SHA, pull request, or release subject;
- source payload or artifact digest;
- native tool, version, rule, check, package, or finding identifiers;
- collection timestamp and completeness state;
- policy ID and digest;
- verdict, reason code, and verifier manifest digest;
- verification status.

The normative `source-v0` identity-completeness rule is documented in
[Source Contract](SOURCE_CONTRACT.md).

## Adoption sequence

Existing scanners, SBOM tools, and CI remain in place. Start with read-only
GitHub metadata, add an explicit external source only for a recurring decision
gap, keep the gate advisory while measuring noise, and enable enforcement only
after repository owners accept the policy and rollback path.

## Market-entry effect

Interoperability lowers switching cost: AOS can consume existing signals
without replacing their producers. That is a product hypothesis, not proof of
demand or economic value. Public claims remain bounded by the
[Hybrid Value Gate](../benchmarks/value/ASSESSMENT.md).

## Source references

- SLSA specification: https://slsa.dev/spec/v1.2/
- SPDX specifications: https://spdx.dev/use/specifications/
- CycloneDX specification overview: https://cyclonedx.org/specification/overview/
- GitHub SARIF support: https://docs.github.com/en/code-security/reference/code-scanning/sarif-files/sarif-support
- OASIS SARIF 2.1.0: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
- in-toto Attestation Framework: https://github.com/in-toto/attestation/blob/main/spec/README.md
- OpenSSF Scorecard: https://github.com/ossf/scorecard
