# Roadmap

## Current status

Current public release: `v0.38.0`.

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

## Stable surface and product experiments

The established zero-config Action and control-assurance contracts remain
frozen for validation. `preflight`, `collect`, `import`, `agent-action`,
`evaluate`, `run`, `check-pr`, `verify`, `summarize`, `export`, and
`bench-verify` retain their semantics, as do `source-v0`, `agent-action-v0`,
and `benchmark-case-v0`.

`aos-check` remains the simple entry utility. It removes Git, GitHub, policy,
and command-discovery knowledge from the first run, but familiar build/test
orchestration is not treated as primary differentiation.

`prove-change` is the selected next product experiment. It is a plug-in after
an existing targeted test command and asks whether the tests still pass when
the actual PR implementation patch is removed. The exploratory eight-case
benchmark supports the mechanism and a narrow eligibility rule, not user value:
run it for code-and-test PRs or an explicitly declared behavior change; skip
behavior-preserving and performance-only changes by default.

No default enablement, dashboard, SaaS layer, broad adapter catalog, or paid
offer should precede external measurement of warning acceptance,
decision-change rate, incremental weak-test findings, runtime cost, noise,
setup time, and four-week retention.

## Next milestone: external value validation

The free advisory release is the recruitment and observation channel.
Progress requires evidence from independent users, not additional internal
automation.

Required sequence:

1. Keep installation and first diagnosis below five minutes.
2. Offer Change Proof only as an opt-in plug-in after a targeted test command.
3. Collect at least 50 eligible PR runs across five independent repositories.
4. Measure accepted test improvements, merge-decision changes, incremental
   findings, noise, inconclusive runs, setup time, runtime cost, and retention.
5. Compare with ordinary CI, patch coverage, and established mutation tooling
   already used by each repository.
6. Run the preregistered formative study when 8-12 independent developers and
   control owners become available.
7. Test organization-level demand only after the developer plug-in produces
   repeated accepted value.
8. Retain `NO_GO` for efficacy, production, ROI, or paid-value claims until the
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
