# Roadmap

## Current status

Current public release: `v0.37.1`.

The CLI and GitHub Action are available as a free, self-serve advisory preview.
The mechanism is deterministic, exact-SHA bound, tamper-evident, and replayable.
The formal product-claim status remains
[`NO_GO`](benchmarks/value/ASSESSMENT.md): external usefulness, precision,
retention, incident reduction, and willingness to pay have not been
independently established.

## Completed foundations

### Phase 0: public boundary

Completed: scope, claim boundaries, architecture, examples, repository hygiene,
and public-surface checks.

### Phase 1: local deterministic gate

Completed: `evaluate`, `verify`, canonical decision records, fail-closed
input handling, tamper detection, and historical replay.

### Phase 2: advisory GitHub Action

Completed: read-only composite Action, advisory default, Markdown and HTML
views, outputs, evidence upload, explicit enforcement, and self-gated releases.

### Phase 3: bounded collection and policy surface

Implemented within the current scope:

- zero-config exact-SHA GitHub collection;
- rulesets and classic branch-protection requirement discovery;
- Check Runs, Check Suites, Workflow Runs, and commit statuses;
- preflight diagnostics and collection completeness;
- SARIF, Scorecard, `source-v0`, and `agent-action-v0` inputs;
- starter policy packs;
- verifier-change independence signal;
- offline benchmark and adversarial replay.

A GitLab API collector and GitLab CI/CD Catalog component are not implemented.

## Correctness and trust program

The v0.30-v0.36 program is implemented:

1. app-bound control identity, separate requirement provenance, and exact-SHA
   observation scope;
2. missing-run, approval-required, stale, incomplete, and unverifiable states;
3. one shared low-noise diagnosis with a dominant problem and next action;
4. content-addressed verifier manifest and backward-compatible replay;
5. automated exact-contrast and adversarial corpora;
6. deterministic remediation coverage;
7. clean-room packaging, threat model, rollback, pinning, and claim boundaries;
8. internal red-team and product-test readiness gates.

These controls establish mechanism behavior and testability, not market value.

## Scope lock

The existing command and contract surface remains frozen for validation:
`preflight`, `collect`, `import`, `agent-action`, `evaluate`, `run`,
`check-pr`, `verify`, `summarize`, `export`, and `bench-verify`, plus
`source-v0`, `agent-action-v0`, and `benchmark-case-v0`.

Until external evidence changes the priority, work is limited to correctness,
compatibility, noise reduction, self-serve onboarding, documentation, and claim
accuracy. No new commands, contracts, dashboards, SaaS layer, or broad adapter
catalog should precede validation.

## Next milestone: external value validation

The free advisory release is the recruitment and observation channel.
Progress requires evidence from independent users, not additional internal
automation.

Required sequence:

1. Keep the install-to-diagnosis path below five minutes.
2. Recruit maintainers and platform or DevSecOps owners responsible for real
   repository controls; individual-developer interest alone is not buyer
   validation.
3. Collect opt-in, non-confidential feedback through the public form.
4. When access exists, run the preregistered formative study with 8-12
   independent developers and control owners.
5. Measure comprehension and next-action clarity, then separately measure
   actionable rate, decision-change rate, incremental findings, repeated
   noise, time-to-resolution, and 30-day retention.
6. Run the comparative signal study only with frozen selection,
   classification, stopping, and claim rules.
7. Test organization-level demand for control drift, exception governance,
   evidence retention, and assurance reporting before defining a paid offer.
8. Retain `NO_GO` for efficacy, production, or paid-value claims until the
   corresponding thresholds are met.

The outcome may be promotion, policy narrowing, repositioning, or product
closure. A technically correct mechanism is not sufficient evidence to
continue commercialization.

## Deferred

Deferred until validated demand or a specific operator requirement exists:

- hosted dashboard, organization analytics, or telemetry;
- cross-repository control inventory, drift, exception governance, and
  assurance reporting;
- any paid product, including policy or evidence services;
- GitLab collection;
- official RafineriaAI signing or provenance service;
- SBOM generation, SLSA level, or compliance automation;
- automatic remediation or code generation;
- LLM participation in the verdict path.

Unsigned in-toto Statement export already exists, but it remains an
`UNSIGNED_NOT_OFFICIAL` projection rather than an attestation.
