# aos-workflow-gate

Evidence-based workflow gate for CI, PR, scanner, and AI-agent signals.

This repository is the workflow layer around `aos-kernel`. Its job is to make a pull request or release gate explainable and replayable: collect workflow signals, apply an explicit policy, and produce a `PASS`, `WARN`, or `BLOCK` decision with evidence.

## Current status

Phase 2: the local `evaluate` CLI and the advisory GitHub Action are implemented. The gate turns a signal bundle plus an explicit policy into a deterministic `PASS`, `WARN`, or `BLOCK` decision record that is replayable and tamper-evident, locally and in pull requests. Signal adapters (Phase 3) are planned next.

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

The draft input and policy files are [examples/github-pr-signal-bundle.json](examples/github-pr-signal-bundle.json) and [policies/default.yml](policies/default.yml).

## GitHub Action

Run the gate in a pull request in advisory mode. The action is read-only, needs
no repository secrets, writes a Markdown summary to the job page, and exposes
the decision record for artifact upload:

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
    uses: RafineriaAI/aos-workflow-gate@v0.2.0
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
