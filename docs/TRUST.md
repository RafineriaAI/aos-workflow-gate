# Trust: verify it yourself

Every claim below comes with a way to check it without trusting us.
These read-only claims cover the default Action, collectors, and replay path.
Experimental `prove-change` deliberately executes operator-supplied project
code in disposable worktrees and has a separate boundary documented in
[Executable Change Proof](CHANGE_PROOF.md) and
[Security Readiness](SECURITY_READINESS.md).

## What the gate can and cannot do to your environment

- **Read-only by design.** Self-Test Mode needs `contents: read`,
  `checks: read`, `actions: read`, `pull-requests: read`, and
  `statuses: read`. No `write` scope of any kind. Verify the
  [README](../README.md) and self-test workflow.
- **No data leaves your environment through the gate.** Network calls are
  read-only requests to your configured GitHub host using your workflow
  token. There is no telemetry, analytics, or phone-home. Verify all call
  sites with `grep -R "_request_json" aos_workflow_gate/`.
- **Zero runtime dependencies.** The package depends on the Python standard
  library only, so there is no transitive supply chain to audit. Verify:
  `dependencies = []` in [pyproject.toml](../pyproject.toml).
- **Reviewable boundaries.** Collection, contracts, evaluation, evidence, and
  presentation are separate typed modules under `aos_workflow_gate/`.
  [Architecture](ARCHITECTURE.md) and the
  [development map](DEVELOPMENT.md) identify each owner; CI runs strict mypy.

## What the evidence provides

- **Deterministic.** The same canonical bundle, policy, and verifier artifact
  produce the same record. Verify: run `evaluate` twice with one installed
  version and compare the files.
- **Tamper-evident.** Any change to a record breaks its self-digest.
  Verify: edit one character in a record and run `verify` (exit 1,
  `TAMPERED`).
- **Replayable offline.** A committed record can be re-checked against its
  bundle with no network. Verify: `verify --input --bundle` on the
  committed examples, or the
  [real-repository case study](case-studies/aos-kernel-release-surface-replay.md).

## What UNSIGNED_NOT_OFFICIAL means

Decision records are structure- and replay-checkable but carry no
signature from us. You can sign exported in-toto Statements with your own
keys (see [DECISION_PREDICATE.md](DECISION_PREDICATE.md)); such a signature
is your claim, not ours.

**AOS Verdict Seal** is a reserved product designation of the copyright
holder for a future officially signed verdict capability. No artifact
produced by this repository today carries the AOS Verdict Seal, no signing
service exists yet, and nothing here should be represented as sealed or
officially verified.

## What is enforced by CI, not by promise

The repository's public-surface guard
([tools/check_public_surface.py](../tools/check_public_surface.py)) fails
CI when documentation drifts from implementation: the document and artifact
index, local links, CLI examples, release pins, permission examples,
claim-boundary wording, contributor controls, and committed replayable
fixtures are checked. The honesty of this page is itself a guarded surface.
