# aos-workflow-gate

Evidence-based workflow gate for CI, PR, scanner, and AI-agent signals.

This repository is the workflow layer around `aos-kernel`. Its job is to make a pull request or release gate explainable and replayable: collect workflow signals, apply an explicit policy, and produce a `PASS`, `WARN`, or `BLOCK` decision with evidence.

## Current status

Public bootstrap. The repository currently defines the product boundary, adoption model, draft example inputs, and first release plan. The executable CLI and GitHub Action are planned next.

No production, compliance, signing, SLSA, or security-audit claim is made by this repository at this stage.

## Core idea

A normal CI dashboard tells you which checks passed. `aos-workflow-gate` is intended to answer a stricter question:

> Given this exact PR, policy, commit, and set of workflow signals, why did the release gate decide `PASS`, `WARN`, or `BLOCK`?

That turns gate behavior from a scattered set of green and red checks into a replayable decision record.

## Practical use case

A maintainer wants a release candidate to be blocked when required checks are missing, warned when non-blocking scanners report known risks, and passed only when required evidence is present.

The planned first CLI shape is:

```bash
aos-workflow-gate evaluate \
  --input examples/github-pr-signal-bundle.json \
  --policy policies/default.yml \
  --out evidence/gate-decision.json
```

Expected output shape:

```json
{
  "verdict": "WARN",
  "subject": {
    "repo": "owner/repo",
    "sha": "abc123"
  },
  "policy": "default",
  "verification_status": "UNSIGNED_NOT_OFFICIAL",
  "summary": "Required checks passed; advisory scanner warnings remain."
}
```

The command above documents the target interface. It is not implemented yet. The draft input and policy files are available in [examples/github-pr-signal-bundle.json](examples/github-pr-signal-bundle.json) and [policies/default.yml](policies/default.yml).

## What this is

- A deterministic gate over workflow evidence.
- A policy and evidence layer for CI, PR, scanner, and AI-agent signals.
- A practical bridge between `aos-kernel` verdict semantics and real repository workflows.
- A future GitHub Action and local CLI that can run in advisory mode before it blocks anything.

## What this is not

- Not a claim that a repository is secure.
- Not a compliance certification system.
- Not a replacement for code review, testing, threat modeling, or release engineering.
- Not a runtime proof that workflow systems are correct.
- Not a signing or provenance authority.

## Documentation map

- [Scope](docs/SCOPE.md) defines claim boundaries and non-goals.
- [Architecture](docs/ARCHITECTURE.md) defines the planned layers.
- [Use cases](docs/USE_CASES.md) gives the first practical workflow scenarios.
- [Adoption guide](docs/ADOPTION_GUIDE.md) removes terminology and integration barriers.
- [Roadmap](ROADMAP.md) defines the phased plan.
- [Draft signal bundle](examples/github-pr-signal-bundle.json) and [draft policy](policies/default.yml) make the first use case concrete.
- [Security policy](SECURITY.md) defines responsible reporting boundaries.
- [Contributing](CONTRIBUTING.md) defines contribution expectations.

## Local check

Run the public surface check with:

`ash
python tools/check_public_surface.py
`

This check validates the documentation index, bootstrap claim boundary, and draft example files. It is not a product audit.

## Relationship to aos-kernel

`aos-kernel` remains the minimal public kernel and formal surface. `aos-workflow-gate` is the operational layer that will adapt real workflow signals into a gate decision record. Kernel correctness claims do not automatically extend to this repository.

## License

MIT. See [LICENSE](LICENSE).
