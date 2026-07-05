# aos-workflow-gate

Evidence-based workflow gate for CI, PR, scanner, and AI-agent signals.

This repository is the workflow layer around `aos-kernel`. Its job is to make a pull request or release gate explainable and replayable: collect workflow signals, apply an explicit policy, and produce a `PASS`, `WARN`, or `BLOCK` decision with evidence.

## Current status

Phase 2: the local `evaluate` CLI and the advisory GitHub Action are implemented. Phase 3 has started: the zero-config GitHub check-runs collector is implemented, so the action can gate a pull request without any hand-written input. The gate turns collected signals plus an explicit policy into a deterministic `PASS`, `WARN`, or `BLOCK` decision record that is replayable and tamper-evident. Further signal adapters (SARIF, Scorecard summaries) are planned next.

Decision records carry `UNSIGNED_NOT_OFFICIAL` verification status: they are structure- and replay-checkable, not an official signed verdict.

No production, compliance, signing, SLSA, or security-audit claim is made by this repository at this stage.

## Core idea

A normal CI dashboard tells you which checks passed. `aos-workflow-gate` is intended to answer a stricter question:

> Given this exact PR, policy, commit, and set of workflow signals, why did the release gate decide `PASS`, `WARN`, or `BLOCK`?

That turns gate behavior from a scattered set of green and red checks into a replayable decision record.

## Practical use case

A maintainer wants a release candidate to be blocked when required checks are missing, warned when non-blocking scanners report known risks, and passed only when required evidence is present.

Run the gate locally:

```bash
python -m pip install -e .
aos-workflow-gate evaluate \
  --input examples/github-pr-signal-bundle.json \
  --policy policies/default.yml \
  --out examples/gate-decision.json
```

This prints the verdict and writes a full decision record. For the committed example the verdict is `WARN`: the required check passed and one advisory scanner warning remains. The record preserves subject identity, policy identity and digest, input identities and digests, the explained reasons, and a self-digest for tamper detection. A committed copy is checked in at [examples/gate-decision.json](examples/gate-decision.json).

Verify a decision record has not been altered:

```bash
aos-workflow-gate verify \
  --input examples/gate-decision.json \
  --bundle examples/github-pr-signal-bundle.json
```

Render a record as Markdown (the same summary the GitHub Action posts):

```bash
aos-workflow-gate summarize --input examples/gate-decision.json
```

Export a verified record as an unsigned in-toto Statement and sign it with
your own keys (see [docs/DECISION_PREDICATE.md](docs/DECISION_PREDICATE.md)):

```bash
aos-workflow-gate export \
  --input examples/aos-kernel-gate-decision.json \
  --out gate-statement.json
cosign sign-blob --yes gate-statement.json \
  --output-signature gate-statement.sig
```

The draft input and policy files are [examples/github-pr-signal-bundle.json](examples/github-pr-signal-bundle.json) and [policies/default.yml](policies/default.yml).

## GitHub Action

Self-Test Mode (zero-config) — an advisory self-test of your pipeline,
without writing any bundle or policy. The action collects the completed
check runs of the current commit, generates an explicit advisory policy
over them, and writes a replayable decision record plus a Markdown summary
to the job page. This is a complete workflow file — copy it as
`.github/workflows/aos-self-test.yml`. No checkout is needed: Self-Test
Mode reads check runs through the API and installs from the action itself:

```yaml
name: AOS Self-Test

on:
  pull_request:

permissions:
  contents: read
  checks: read

jobs:
  self-test:
    runs-on: ubuntu-latest
    steps:
      # Pinned from actions/setup-python@v6 on 2026-07-03.
      - uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1
        with:
          python-version: "3.11"
      - name: AOS self-test (advisory)
        uses: RafineriaAI/aos-workflow-gate@v0.9.0
        with:
          required-checks: "ci / validate"
```

`checks: read` is needed because a `permissions:` block sets every unlisted
scope to `none`, and zero-config mode reads the commit's check runs through
the workflow token. Public repositories happen to work without it; private
repositories do not.

`required-checks` is optional; named checks become required (missing or
failed means `BLOCK`), every other collected check is advisory. Set
`wait-for-checks: "120"` to poll until the required checks complete (only
required checks are waited for; a wait that ends incomplete fails closed
and is recorded in the bundle's collection status). The generated bundle
and policy are written to `.aos-gate/` so the decision stays replayable.

For full control, provide an explicit bundle and policy. The action is
read-only, needs no repository secrets, writes a Markdown summary to the job
page, and exposes the decision record for artifact upload:

```yaml
permissions:
  contents: read

steps:
  # Pinned from actions/checkout@v5 on 2026-07-03.
  - uses: actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd
    with:
      persist-credentials: false
  # Pinned from actions/setup-python@v6 on 2026-07-03.
  - uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1
    with:
      python-version: "3.11"
  - name: Run gate (advisory)
    id: gate
    uses: RafineriaAI/aos-workflow-gate@v0.9.0
    with:
      input: examples/github-pr-signal-bundle.json
  # Pinned from actions/upload-artifact@v7.0.1 on 2026-07-04.
  - name: Upload decision record
    uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
    with:
      name: gate-decision
      path: gate-decision.json
```

Advisory mode never fails the job; the verdict is reported in the step summary
and in the `verdict` output. Set `enforce: "true"` to make a `BLOCK` verdict
fail the step. This repository runs the action on itself in
[.github/workflows/aos-workflow-gate-self.yml](.github/workflows/aos-workflow-gate-self.yml).

## Platform neutrality

The gate core is platform-neutral: plain Python, zero runtime dependencies,
JSON in and out. GitHub Enterprise Server works out of the box, and GitLab
CI or Jenkins can run the same evaluation on an explicitly provided bundle —
see [docs/CI_INTEGRATIONS.md](docs/CI_INTEGRATIONS.md). Only the check-runs
collector and the Action are GitHub-specific by design.

## What this is

- A deterministic gate over workflow evidence.
- A policy and evidence layer for CI, PR, scanner, and AI-agent signals.
- A practical bridge between `aos-kernel` verdict semantics and real repository workflows.
- A GitHub Action and local CLI that run in advisory mode before they block anything.

## What this is not

- Not a claim that a repository is secure.
- Not a compliance certification system.
- Not a replacement for code review, testing, threat modeling, or release engineering.
- Not a runtime proof that workflow systems are correct.
- Not a signing or provenance authority.

## Documentation map

- [Scope](docs/SCOPE.md) defines claim boundaries and non-goals.
- [Architecture](docs/ARCHITECTURE.md) defines the layers and what each phase implements.
- [Use cases](docs/USE_CASES.md) gives the first practical workflow scenarios.
- [Adoption guide](docs/ADOPTION_GUIDE.md) removes terminology and integration barriers.
- [Standards compatibility](docs/STANDARDS_COMPATIBILITY.md) maps planned integrations to SLSA, SPDX, CycloneDX, SARIF, in-toto, and OpenSSF Scorecard without claiming compliance.
- [Decision record predicate](docs/DECISION_PREDICATE.md) defines the in-toto Statement export and operator-key signing recipe.
- [CI integrations](docs/CI_INTEGRATIONS.md) covers GitHub Enterprise Server, GitLab CI, and generic shell usage.
- [Trust](docs/TRUST.md) shows how to verify every claim yourself: read-only permissions, no telemetry, zero dependencies, tamper evidence, offline replay.
- [Buyer FAQ](docs/BUYER_FAQ.md) answers security reviewers: data flows, permissions, free vs paid, vendor risk, platform coverage.
- [Security readiness](docs/SECURITY_READINESS.md) documents the private-repo data model and implemented input hardening, each with a negative test.
- [Real-repository replay case study](docs/case-studies/aos-kernel-release-surface-replay.md) runs the gate on real workflow signals at a pinned commit and replays the committed decision offline.
- [Roadmap](ROADMAP.md) defines the phased plan.
- [Release governance](docs/RELEASE_GOVERNANCE.md) defines branch, ruleset, tag, and release policy.
- [Draft signal bundle](examples/github-pr-signal-bundle.json) and [draft policy](policies/default.yml) make the first use case concrete.
- [Security policy](SECURITY.md) defines responsible reporting boundaries.
- [Contributing](CONTRIBUTING.md) defines contribution expectations.

## Local check

Run the local hygiene checks with:

```bash
python -m ruff check .
python -m mypy
python -m pytest
python tools/check_public_surface.py
```

Or run only the public surface check with:

```bash
python tools/check_public_surface.py
```

This check validates the documentation index, bootstrap claim boundary, and draft example files. It is not a product audit.

## Relationship to aos-kernel

`aos-kernel` remains the minimal public kernel and formal surface. `aos-workflow-gate` is the operational layer that will adapt real workflow signals into a gate decision record. Kernel correctness claims do not automatically extend to this repository.

## License

Apache-2.0. See [LICENSE](LICENSE).

The license covers this repository's source code only. It grants no rights
to the "AOS", "AOS Kernel", or "RafineriaAI" names and marks, and no rights
to the separate proprietary AOS Core technology. See [NOTICE](NOTICE).
