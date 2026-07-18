# Release Governance

This repository publishes a standalone workflow product in the AOS product
family. Release controls protect this repository's own implementation without
claiming production readiness, compliance, official signing, supply-chain
attestation, or correctness of external CI, scanner, or agent systems.

## Current Release Boundary

The current line is a free public advisory preview. It may claim deterministic
policy evaluation, exact-SHA collection, canonical digests, tamper detection,
content-addressed verifier disclosure, and offline replay because those
mechanisms are implemented and tested.

It must not claim independently validated precision, practical usefulness,
incident reduction, production suitability, retention, or willingness to pay.
Those claims remain controlled by the
[Hybrid Value Gate](../benchmarks/value/ASSESSMENT.md), currently `NO_GO`.
The phase sections below preserve the release history and cumulative boundary.

## Phase 0 Release Boundary

Phase 0 is repository hygiene and public boundary work only. It may define documents, examples, policies, tests, and CI checks, but it must not claim an implemented gate, production enforcement, signed evidence, SLSA compliance, or security-audit certification.

Unlike `aos-kernel`, no Lean build is required in this repository. The
kernel's interval-gate formal surface does not prove this repository's
workflow evaluator. This repository independently owns and tests workflow
inputs, policy semantics, evidence records, replay, and integration behavior.
A future kernel-backed claim requires a versioned shared contract and identical
conformance vectors executed in both repositories; shared vocabulary and
design lineage are not sufficient.

## Phase 1 Release Boundary

Phase 1 adds the local `evaluate` and `verify` CLI. A release may now claim a local, deterministic, replayable gate decision with a tamper-evident record. It must still not claim production enforcement, signed or official evidence, SLSA or SBOM provenance, security-audit certification, or that a `PASS` means a repository is secure, correct, production-ready, or legally compliant. Decision records remain `UNSIGNED_NOT_OFFICIAL`.

## Phase 2 Release Boundary

Phase 2 adds the advisory GitHub Action around the Phase 1 evaluation. A release may now claim an advisory pull-request gate with a Markdown summary and a replayable decision artifact. Advisory mode must stay the default; a release must not claim production enforcement, and enforcement remains an explicit per-workflow opt-in (`mode: "enforce"` or a blocking policy; `enforce: "true"` is a deprecated Action alias). All Phase 1 boundary limits continue to apply.

## Immutable Release Tags

Release tags are immutable once pushed to `origin`.

Do not delete, recreate, or force-push a published `v*` tag. Do not use `git push --force --tags`, `git tag -d <tag>` followed by remote deletion, or any other retag flow for a public release.

If a release tag is wrong, leave the original tag in place and publish a new patch release with a correction note. The GitHub Release text may add a clearly dated erratum, but the tag target must not move.

Use annotated SemVer tags for public releases, for example:

```bash
git tag -a v0.1.0 -m "AOS Workflow Gate v0.1.0"
git push origin v0.1.0
```

## Candidate Version vs Published Version

`aos_workflow_gate/version.py` and `pyproject.toml` identify the current
package candidate. `docs/PUBLISHED_VERSION` identifies the newest immutable
GitHub tag that public installation examples may reference. The candidate
may be newer than the published version; the reverse is invalid.

This separation prevents a merged version bump from breaking the public
quickstart before its tag exists. `tools/check_public_surface.py` requires
every public `uses:` and Git install example to match
`docs/PUBLISHED_VERSION`, not the unreleased candidate.

Release sequence:

1. Merge and verify the candidate without pointing users at a missing tag.
2. Create the immutable tag and publish the release after all release gates
   pass.
3. In a follow-up change, update `docs/PUBLISHED_VERSION` and every public
   installation example to that tag.

## Public Merge Metadata

The final merge commit is part of the permanent public release surface. Do
not accept GitHub's default `Merge pull request ... from ...` message because
it publishes the temporary head-branch name. Merge release-facing changes
with an explicit, outcome-oriented subject and body:

```bash
gh pr merge <number> --merge \
  --subject "<public outcome>" \
  --body "<public rationale>" \
  --delete-branch
```

The subject and body must describe shipped behavior, contain no temporary
branch prefix, and make sense without repository-operation context. On pushes
to `main`, CI runs `tools/check_public_surface.py --check-head-commit` and
rejects default merge subjects that expose a branch name.

## Required Repository Controls

Before publishing a public release, manually verify the repository-hosted settings because local validation cannot prove them.

Recommended `main` protection:

- active branch ruleset or branch protection rule targeting `main`;
- required status check: `AOS Workflow Gate CI / validate` from GitHub Actions;
- strict/up-to-date status checks when practical;
- pull request required before merge for non-emergency changes;
- force pushes and deletions blocked;
- no routine admin bypass for release commits.

Recommended release tag protection:

- active tag ruleset targeting `v*`;
- restrict updates and deletions;
- restrict creations to release maintainers if the repository role allows it;
- block force pushes.

If a tag ruleset is not yet configured, this documented no-retag policy is the minimum public repository policy. It is weaker than enforced tag protection and must be called out during release review.

## Self-Gated Releases

Every `v*` tag push triggers the release-gate workflow
(`.github/workflows/aos-workflow-gate-release-gate.yml`): the gate gates
its own release in **enforce mode**, requiring this repository's own
required status check on the tagged commit (waiting up to 10 minutes for
CI still in flight). A failed release gate means the GitHub Release must
not be published.

The decision record, bundle, and generated policy for the release commit
are attached to the GitHub Release as assets, so every release ships with
its own replayable gate decision. The workflow stays read-only
(`contents: read`, `checks: read`, `actions: read`, and
`statuses: read`); publishing the release and
attaching assets remain maintainer steps outside CI, per the permissions
contract.

## GitHub Release Publication

GitHub Releases should be published only after the release tag exists, the final commit CI is green, and the local public-surface check passes.

Release text must keep the same public boundary as the repository:

- standalone workflow gate, not a kernel proof or kernel-backed verdict;
- `UNSIGNED_NOT_OFFICIAL` until signing and publication controls exist;
- no production, compliance, security-audit, signing, SBOM, SLSA, or attestation claim unless the corresponding audited infrastructure exists;
- no claim that `PASS` means a repository is secure, correct, production-ready, or legally compliant.

## Operational Handoff

`aos-kernel` remains a separate reference demonstrator with an abstract
interval-verdict proof surface. `aos-workflow-gate` is a standalone product
implementation that shares AOS vocabulary and design principles but no runtime
or formal guarantee. Workflow adapters, policies, records, and integrations
must remain explicit, tested, and documented in this repository.
