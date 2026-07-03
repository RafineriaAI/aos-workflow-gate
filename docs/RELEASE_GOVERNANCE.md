# Release Governance

This repository publishes the workflow gate layer around `aos-kernel`. Release process controls are intentionally narrow: they protect the public workflow-gate surface without claiming production readiness, compliance, official signing, supply-chain attestation, or correctness of external CI/scanner/agent systems.

## Phase 0 Release Boundary

Phase 0 is repository hygiene and public boundary work only. It may define documents, examples, policies, tests, and CI checks, but it must not claim an implemented gate, production enforcement, signed evidence, SLSA compliance, or security-audit certification.

Unlike `aos-kernel`, no Lean build is required in this repository. Formal verdict semantics remain in the kernel. This repository owns workflow inputs, policy evaluation shape, evidence output shape, and integration hygiene.

## Immutable Release Tags

Release tags are immutable once pushed to `origin`.

Do not delete, recreate, or force-push a published `v*` tag. Do not use `git push --force --tags`, `git tag -d <tag>` followed by remote deletion, or any other retag flow for a public release.

If a release tag is wrong, leave the original tag in place and publish a new patch release with a correction note. The GitHub Release text may add a clearly dated erratum, but the tag target must not move.

Use annotated SemVer tags for public releases, for example:

```bash
git tag -a v0.1.0 -m "AOS Workflow Gate v0.1.0"
git push origin v0.1.0
```

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

## GitHub Release Publication

GitHub Releases should be published only after the release tag exists, the final commit CI is green, and the local public-surface check passes.

Release text must keep the same public boundary as the repository:

- workflow gate layer, not kernel proof;
- `UNSIGNED_NOT_OFFICIAL` until signing and publication controls exist;
- no production, compliance, security-audit, signing, SBOM, SLSA, or attestation claim unless the corresponding audited infrastructure exists;
- no claim that `PASS` means a repository is secure, correct, production-ready, or legally compliant.

## Operational Handoff

`aos-kernel` remains the minimal kernel and formal verdict surface. `aos-workflow-gate` may develop workflow adapters, policies, evidence records, and integration tooling only when those behaviors are explicit, tested, and documented.
