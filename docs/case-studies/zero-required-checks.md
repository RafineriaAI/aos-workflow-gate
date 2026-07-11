# Merge-ready with zero enforced evidence

The main aha case, from this repository's own history: **GitHub's
required status checks permitted the merge while zero checks were
required at the gate — and the gate's very first advisory record says
so, with the failures named.** (Scope: required status checks, not
full merge-readiness — reviews, merge queues, and bypass actors are
outside what is evaluated.)

## The real state

Commit
[`f8c6517`](https://github.com/RafineriaAI/aos-workflow-gate/commit/f8c6517bef32e68d3150d2954cc4c445b6fb1642)
is the merge that shipped as `v0.11.0` — the release where a broken
`action.yml` went out. At that commit, GitHub's persisted check runs
show:

| Check | Conclusion |
| --- | --- |
| `AOS Workflow Gate CI / validate` | success |
| `AOS Workflow Gate Self / advisory` | **failure** |
| `AOS Workflow Gate Self / zero-config` | **failure** |
| `AOS Workflow Gate Self / no-checkout` | skipped |

The one required check was green, so the pull request was merge-ready
and the merge went through. Both self-test jobs — the ones that
actually exercised the broken file — failed, and nothing required them.

## What the default gate run says

This is exactly the state every fresh adopter starts in: the
zero-config first run generates an advisory policy with **zero required
sources**. Against the same real commit it produces
([record](../../examples/zero-required-record.json),
[bundle](../../examples/zero-required-bundle.json),
[policy](../../examples/zero-required-policy.json)):

```text
WARN  Gate WARN: the policy requires nothing, so nothing can block; 4 warning(s).
Signals: 0 required (0 successful) · 4 advisory (3 warning(s))
Can block this job: no
```

with the decision gap itself raised as an explicit `no_required_sources`
warning — zero required plus green checks would still be `WARN`, never
a quiet `PASS` — the two real failures named as reasons, and the
Coverage section stating the gap in one sentence: *no source is required, so a
missing or failed check cannot make this gate BLOCK — the record is
evidence, not enforcement.*

A `WARN` is the honest verdict here — under a policy that requires
nothing, nothing can block, and the gate says that instead of
pretending. The repair is one line (`required-checks:` naming the
self-test), and the
[governance benchmark's counterfactual case](../../benchmarks/cases/v0110-incident-counterfactual/)
shows the same commit turning into a named `BLOCK` once the self-test
is required.

## Replay it yourself

```bash
pip install "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.32.0"
aos-workflow-gate verify \
  --input examples/zero-required-record.json \
  --bundle examples/zero-required-bundle.json
aos-workflow-gate summarize --input examples/zero-required-record.json
```

The record replays offline from the committed files; the test suite
replays it on every CI run.

## Boundary

The signals are real and persisted by GitHub for the exact commit; the
gate run is retrospective (collected at case-assembly time). `WARN`
here shows visibility, not a vulnerability, and makes no security claim
about the repository. Decision records carry `UNSIGNED_NOT_OFFICIAL`
status.
