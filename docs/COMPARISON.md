# Comparison: What Each Decision Layer Answers

A capability matrix, **not a ranking**: different tools answer different
questions, and the gate is designed to consume most of them as signals
rather than replace them. Every cell describes documented behavior with a
source link; no competitor tool was benchmarked or scored here, and no
superiority is claimed.

## The questions that matter at gate time

| Question | Branch protection / rulesets | OPA / conftest | in-toto attestations | aos-workflow-gate |
| --- | --- | --- | --- | --- |
| What artifact does a decision produce? | UI state and merge refusal; no exportable decision artifact ([docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)) | Process exit code and console output per policy test ([docs](https://www.conftest.dev/)) | A signed statement binding a predicate to an artifact ([spec](https://github.com/in-toto/attestation/blob/main/spec/README.md)) | A decision record: subject, policy digest, input digests, reasons, self-digest |
| Is the decision replayable offline later? | No stored decision to replay | Re-run requires the same inputs and policy at hand; no self-verifying record | Yes — signature verification of the statement | Yes — `verify` re-checks record and bundle with no network |
| Is the policy an inspectable artifact? | Settings state, exportable via API, not versioned by default | Yes — Rego files | Policy lives in the verifier configuration ([in-toto verification](https://github.com/in-toto/attestation/blob/main/docs/validation.md)) | Yes — YAML/JSON file whose digest is embedded in every record |
| Does it distinguish "did not run" from "ran and passed"? | Required checks block on missing; non-required checks show no difference at a glance | Only if the policy author models it | Absence of an attestation is detectable by the verifier | Yes - required skipped checks affect the verdict; non-required results remain recorded and an explicit policy can promote them ([case study](case-studies/green-but-incomplete.md)) |
| What does an auditor receive? | Screenshots or API exports of settings and check pages | CI logs of policy runs | Signed statements plus verifier logs | One committed record per decision plus a one-command replay |
| Signed by an authority? | Platform-internal | No signing model of its own | Yes — that is its core design | No — `UNSIGNED_NOT_OFFICIAL`; operator-key signing via in-toto export |

## Complementary by design

The gate consumes these layers instead of competing with them: branch
protection defines which checks exist (our first case study's policy
mirrors a real ruleset), conftest-style policy runs can enter the bundle
as sources like any check, and the gate's own records export as in-toto
Statements for operator-key signing
([DECISION_PREDICATE.md](DECISION_PREDICATE.md)). If you need signed
provenance of builds, use in-toto/SLSA tooling; if you need Rego's
expressiveness over structured configs, use conftest — and gate the
outcome.

## Decision-layer illustration

The same scenario, expressed at each layer, from this repository's
committed artifacts: a conftest-style check ends as an exit code in a CI
log; branch protection ends as a merge button state; the gate ends as
[examples/green-but-incomplete-record.json](../examples/green-but-incomplete-record.json)
— a file you can hand to a reviewer a year later and re-verify in one
command.

## Boundary

Cells describe documented behavior as of 2026-07-05 with sources linked;
tools evolve, and corrections are welcome via issues. This document makes
no superiority, security, or compliance claim and assigns no scores.
