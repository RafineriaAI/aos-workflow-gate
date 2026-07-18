# Merge-ready with zero enforced evidence

A historical evidence-gap case from this repository's own history. GitHub
required one status check and permitted the merge because that check passed.
The retrospective AOS policy intentionally requires zero checks and makes
that policy gap explicit. This fixture demonstrates empty-policy semantics;
it is not evidence that current autodiscovery would ignore an active GitHub
requirement.

Scope is required status checks, not full merge-readiness. Reviews, merge
queues, and bypass actors are outside what is evaluated.

## The real state

Commit
[`f8c6517`](https://github.com/RafineriaAI/aos-workflow-gate/commit/f8c6517bef32e68d3150d2954cc4c445b6fb1642)
is the merge that shipped as `v0.11.0`, the release where a broken
`action.yml` went out. At that commit, GitHub's persisted check runs show:

| Check | Conclusion |
| --- | --- |
| `AOS Workflow Gate CI / validate` | success |
| `AOS Workflow Gate Self / advisory` | **failure** |
| `AOS Workflow Gate Self / zero-config` | **failure** |
| `AOS Workflow Gate Self / no-checkout` | skipped |

The one GitHub-required check was green, so GitHub permitted the merge.
Both self-test jobs that exercised the broken file failed, but GitHub did
not require them.

## What the zero-required policy says

The retrospective fixture applies an explicit zero-required advisory policy
to the same commit. Current zero-config collection instead discovers active
GitHub branch requirements whenever that surface is readable.

The committed [record](../../examples/zero-required-record.json),
[bundle](../../examples/zero-required-bundle.json), and
[policy](../../examples/zero-required-policy.json) produce:

```text
AOS Workflow Gate: WARN
What AOS found: This policy requires no checks, so no check result can block the gate.
Effect: advisory only; WARN/BLOCK is reported but does not fail this job
Next: configure at least one required status check in GitHub, or pass required-checks explicitly, then re-run AOS
Signals: 0 required (0 successful); 4 other observation(s)
```

The only alert is the decision gap itself: `no_required_sources`. The two
real failures and the skipped check remain visible in the evidence table,
but do not become duplicate AOS warnings. An explicit policy can still
promote a non-required result when that is intentional.

`WARN` is the honest verdict for this policy: nothing is required, so
nothing can block. The repair is to configure a required GitHub status
check or pass `required-checks`. The
[governance benchmark's counterfactual case](../../benchmarks/cases/v0110-incident-counterfactual/)
shows the same commit turning into a named `BLOCK` once the self-test is
required.

## Replay it yourself

```bash
pip install "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.37.1"
aos-workflow-gate verify \
  --input examples/zero-required-record.json \
  --bundle examples/zero-required-bundle.json
aos-workflow-gate summarize --input examples/zero-required-record.json
```

The record replays offline from the committed files; the test suite replays
it on every CI run.

## Boundary

The check results are real and persisted by GitHub for the exact commit.
The AOS decision is retrospective and uses an explicit empty policy. It
shows deterministic policy-gap handling, not a vulnerability, product
utility, or a claim about current repository settings. Decision records
carry `UNSIGNED_NOT_OFFICIAL` status.