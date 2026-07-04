# Case Study: Real-Repository Release-Surface Replay

This case study runs the gate on real workflow signals from a public
repository at a pinned commit, and shows that the resulting decision record
is replayable offline from the committed files alone.

Subject:

```text
repository: RafineriaAI/aos-kernel
ref:        refs/heads/main
commit:     3c00cddf59ebd233cca4761785e20ad51ac9ed78
```

The policy mirrors how that repository actually protects `main`: the branch
ruleset requires the `AOS Kernel CI / validate` status check, while CodeQL,
actionlint, gitleaks, and OpenSSF Scorecard run as non-required supply-chain
checks. The gate policy maps the required check to `required_sources` and the
rest to `advisory_sources`.

## Method

The signal bundle was exported manually from the GitHub check-runs API on
2026-07-04 (signal adapters are a later phase; the export method is recorded
here so the bundle itself is auditable):

1. Fetch `GET /repos/RafineriaAI/aos-kernel/commits/3c00cd.../check-runs`.
2. For each repository-defined check run, keep the identity subset
   `{check_run_id, name, head_sha, status, conclusion, completed_at}`.
3. Compute each source digest as `sha256:` plus the SHA-256 of the canonical
   JSON encoding of that subset (sorted keys, no insignificant whitespace) —
   the same canonical encoding the gate itself uses.
4. Record the check conclusion as the source status and `completed_at` as
   `observed_at`.

Anyone can re-fetch the same API data for the pinned commit and recompute the
same digests.

## Reproduce the decision

From the repository root:

```bash
python -m pip install -e .
aos-workflow-gate evaluate \
  --input examples/aos-kernel-signal-bundle.json \
  --policy policies/aos-kernel-release-surface.yml \
  --out /tmp/aos-kernel-gate-decision.json
```

Replay the committed decision record fully offline:

```bash
aos-workflow-gate verify \
  --input examples/aos-kernel-gate-decision.json \
  --bundle examples/aos-kernel-signal-bundle.json
```

## Measured results

Metrics follow the kernel repository's proof-of-value template:

| Metric | Value |
| --- | --- |
| Time to first verdict | ~360 ms (whole process, cold start, local machine) |
| Verdict | `PASS` |
| Signal count | 5 (1 required, 4 advisory) |
| Record SHA-256 availability | yes (`record_digest` in the committed record) |
| Replay success | yes (`verify` returns `OK` against the committed bundle) |
| Verification status | `UNSIGNED_NOT_OFFICIAL` |
| Operator notes | Policy written directly from the subject repository's branch ruleset; no signal adapter needed for a first real-data record. |

This is the `PASS` path on real data. The committed synthetic example
([examples/github-pr-signal-bundle.json](../../examples/github-pr-signal-bundle.json))
shows the `WARN` path, and the test suite covers `BLOCK` and fail-closed
handling of malformed input.

## What this shows

- A real repository's protection model can be expressed as an explicit,
  inspectable gate policy without new tooling on the subject side.
- Real workflow signals can be reduced to digest-anchored sources, and the
  gate decision over them is deterministic and replayable offline.
- The answer to "why did the gate decide `PASS` for this exact commit" is a
  single self-verifying record, not a reconstruction from CI logs.

## Boundaries

This case study does not establish that the subject repository is secure,
correct, or compliant; it does not establish production readiness, customer
adoption, or willingness to pay; and it does not make the exported GitHub
state itself tamper-proof or complete. The decision record remains
`UNSIGNED_NOT_OFFICIAL`. The export step was manual; automated adapters are
future work and no adapter behavior is claimed.
