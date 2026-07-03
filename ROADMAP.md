# Roadmap

## Phase 0: public bootstrap

Goal: make the repository understandable and auditable before implementation.

- Define scope and non-goals.
- Define first practical use cases.
- Define architecture and adoption model.
- Add draft signal and policy examples for the first use case.
- Add a lightweight public surface check for bootstrap consistency.
- Avoid production, compliance, security-audit, signing, and SLSA claims.

## Phase 1: local MVP CLI

Goal: evaluate a fixed workflow signal bundle against an explicit policy.

Planned command shape:

```bash
aos-workflow-gate evaluate --input examples/github-pr-signal-bundle.json --policy policies/default.yml --out evidence/gate-decision.json
```

Expected properties:

- Deterministic output.
- Stable JSON decision artifact.
- `UNSIGNED_NOT_OFFICIAL` verification status.
- Fail-closed handling for malformed or missing mandatory input.
- Tests for replay, tampering, missing inputs, and edge cases.

## Phase 2: GitHub Action advisory mode

Goal: run the same evaluation in pull requests without blocking by default.

Expected properties:

- Read-only permissions by default.
- No repository secrets required for public data paths.
- Markdown summary for maintainers.
- JSON artifact upload.
- Clear distinction between advisory and blocking modes.

## Phase 3: policy packs

Goal: provide reusable policy profiles without hiding the policy.

Candidate packs:

- Minimal PR gate.
- Release candidate gate.
- AI-agent review governance.
- Scanner-aware advisory gate.

## Phase 4: evidence hardening

Goal: strengthen evidence integrity after the decision contract is stable.

Potential additions:

- Signed decision artifacts.
- Provenance export.
- Optional in-toto or SLSA-aligned evidence mapping.
- Optional SBOM/declaration export.

These are future layers, not current claims.
