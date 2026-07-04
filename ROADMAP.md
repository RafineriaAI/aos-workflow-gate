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

Status: implemented. The `evaluate` and `verify` commands are available and
covered by tests; the committed decision fixture is replayable.

Goal: evaluate a fixed workflow signal bundle against an explicit policy.

Command shape:

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

Status: implemented. The composite action runs `evaluate` in advisory mode by
default, writes a Markdown step summary, exposes verdict and record outputs,
and the repository runs it on itself in CI with the decision record uploaded
as a JSON artifact.

Goal: run the same evaluation in pull requests without blocking by default.

Expected properties:

- Read-only permissions by default.
- No repository secrets required for public data paths.
- Markdown summary for maintainers.
- JSON artifact upload.
- Clear distinction between advisory and blocking modes.

## Phase 3: signal adapters and policy packs

Status: in progress. The zero-config GitHub check-runs collector is
implemented: `collect` builds a signal bundle from the check-runs API with
digest-anchored sources and can generate an explicit advisory policy over
every collected check. GitHub Enterprise Server is supported via
`GITHUB_API_URL`/`GITHUB_SERVER_URL` or `--api-url`. SARIF and Scorecard
summary adapters, a GitLab pipeline-jobs collector, a GitLab CI/CD Catalog
component, and reusable policy packs remain planned.

Goal: provide signal adapters and reusable policy profiles without hiding
the policy.

Candidate packs:

- Minimal PR gate.
- Release candidate gate.
- AI-agent review governance.
- Scanner-aware advisory gate.

## Phase 4: evidence hardening

Status: partially pulled forward. The unsigned in-toto Statement export
(`export`) is implemented, with an operator-key signing recipe documented in
`docs/DECISION_PREDICATE.md`. Official RafineriaAI-signed decision
artifacts, provenance generation, and verification controls remain future
work.

Goal: strengthen evidence integrity after the decision contract is stable.

Potential additions:

- Signed decision artifacts.
- Provenance export.
- Optional in-toto or SLSA-aligned evidence mapping.
- Optional SBOM/declaration export.

These are future layers, not current claims.
