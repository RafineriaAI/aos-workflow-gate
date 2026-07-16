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

Status: in progress. Implemented: the zero-config GitHub check-runs
collector (GHES supported via `GITHUB_API_URL`/`--api-url`), the SARIF
2.1.0 file adapter and the Scorecard presence adapter (mechanical
contracts in `docs/ADAPTERS.md`), and three starter policy packs shipped
in the package (`aos_workflow_gate/packs/`, `docs/POLICY_PACKS.md`). The instant merge-protection check (`check-pr <PR URL>`)
evaluates a policy generated from the base branch's active rules. A
GitLab pipeline-jobs collector and a GitLab CI/CD Catalog component
remain planned.

Goal: provide signal adapters and reusable policy profiles without hiding
the policy.

Candidate packs:

- Minimal PR gate.
- Release candidate gate.
- AI-agent review governance.
- Scanner-aware advisory gate.

## MVP scope lock (v0.22)

Status: locked. The MVP command and contract surface — `preflight`,
`collect`, `import`, `agent-action`, `evaluate`, `run`, `check-pr`,
`verify`, `summarize`, `export`, `bench-verify`, with the `source-v0`,
`agent-action-v0`, and `benchmark-case-v0` contracts and the
retrospective real-history governance benchmark — is complete and
frozen for pre-publication validation. Changes remain limited to
hardening, correctness fixes, documentation, and claim-boundary
corrections: no new commands, contracts, or integrations.

The gate is technically self-contained: advertised mechanics are
implemented, tested, replayable offline, and bounded by explicit claims.
That does not establish incremental user value, acceptable noise, or
pilot readiness. External onboarding and pilot intake remain closed until
the [Hybrid Value Gate](benchmarks/value/ASSESSMENT.md) reaches `GO`.

## Pre-pilot correctness and trust program (v0.30+)

Status: in progress. A maintainer-directed program executed inside the
scope lock's own terms (hardening, correctness fixes, documentation,
and claim-boundary work; no new commands or contracts):

1. GitHub semantic, scope, and freshness correctness — dual-track
   requirement states (`github_equivalent` next to the gate's evidence
   state), rulesets and classic protection unioned, merge_group
   subjects, `observed_at` freshness, and no PASS on an incomplete or
   unknown collection.
2. Workflow state and expected-run visibility — workflows that never
   started become visible; `missing` is only ever relative to an
   explicit expectation.
3. Scope-aware low-noise decision output — one shared diagnosis
   projection: scope, freshness, effect, at most three gaps, one
   dominant problem, one next action; quiet PASS.
4. Evidence-led pain discovery — a frozen, reproducible corpus of
   public pull requests with discovery/holdout separation and recorded
   negative results.
5. Trusted verifier-change awareness — evidence generated solely by a
   mechanism the same change modifies is flagged as not independent
   (advisory by default; no model output in any verdict path).
6. Automated contrast proof — replayable baseline-vs-gate case studies
   generated from the corpus, without selecting only favorable results.
7. Pre-release trust package — threat model, rollback, claim
   boundaries, pinning, and a clean-room install proof.
8. Internal red-team and pilot readiness gate — adversarial regression
   matrix and an explicit GO/NO-GO readiness criterion.

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
