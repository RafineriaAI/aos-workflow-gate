# Real-Agent Governance Benchmark v0

Can a green dashboard hide a governance gap that a deterministic
evidence gate makes explicit? This benchmark measures exactly one
thing: **detection of merge-ready decisions lacking required
evidence**, on real repository history — no staged repositories, no
fabricated signals, no synthetic scenarios.

Every case is built from a real coding-agent change that actually
happened in this repository, with its real pull request diff, the real
check runs GitHub persisted for the exact commits, and a decision
record that replays offline. Cases validate under the
[benchmark harness](../docs/BENCHMARK_HARNESS.md)
(`benchmark-case-v0`), which runs nothing and states its
verified-vs-unverifiable boundary per check.

## Dogfooding boundary — read this first

The coding agent whose changes these cases record is **Claude Code
(Anthropic), operated by the maintainer**, working on **this
repository's own tasks**. The vendor of the gate ran the benchmark on
the vendor's own history: that makes the cases fully auditable and
replayable, and it also means no third-party agent, repository, or
operator has been measured yet. Nothing here generalizes beyond this
repository until someone reproduces the method elsewhere — the format
and harness exist so that anyone can.

## Cases

| Case | GitHub baseline | Gate verdict | What it shows |
| --- | --- | --- | --- |
| [`agent-pr36-preflight`](cases/agent-pr36-preflight/) | merge-ready, all signals green | `PASS` | Control case: baseline and gate agree; no false alarm on a clean agent change. |
| [`green-but-incomplete-pr22`](cases/green-but-incomplete-pr22/) | merge-ready, dashboard fully green | `WARN` | A control that never ran (`skipped`) is named in the record; the gap is invisible on the green dashboard. |
| [`v0110-incident-counterfactual`](cases/v0110-incident-counterfactual/) | merge-ready, required check green | `BLOCK` | The real v0.11.0 incident: the change broke `action.yml`, both self-test jobs failed on the merge commit, the only required check was green — and the release shipped broken. |

All three verdicts come from real, persisted signals. The third case is
a **controlled counterfactual on real history**: the signals are the
incident's own (the failed self-test runs GitHub still serves for that
commit); only the policy choice — requiring the self-test — is
retrospective. That is the incident's actual lesson, stated as a
replayable record instead of a postmortem sentence.

## The measured claim — no more, no less

The two gap cases are different kinds of gap, and the distinction
matters: `v0110-incident-counterfactual` is a **required-evidence gap**
(a required control failed while the baseline said merge-ready —
surfaced as `BLOCK`, 1 of 1 detected), and `green-but-incomplete-pr22`
is an **advisory-visibility gap** (a non-required control silently never
ran — surfaced as a named `WARN`, 1 of 1 detected; a WARN never blocks
anything). On the clean control case the gate raised nothing (0 false
alarms on 1 control). The GitHub merge-ready baseline in each case is
**operator-declared** from historical platform state and marked as such
by the harness — it is not mechanically re-verifiable offline. Three
cases from one repository is a sample, not a study: the numbers above
are counted, not estimated, and no claim is made beyond them.

## Predeclaration and honesty

Each case declares its task, acceptance criteria, and budget, with the
chronology `task_declared < action_captured < decision_evaluated`
checked for internal consistency by the harness. Timestamp truth,
patch authorship, the operator-declared GitHub baseline, and the
operator attestation are explicitly **unverifiable** and reported as
such — see the [harness boundary](../docs/BENCHMARK_HARNESS.md). This
is a **retrospective real-history benchmark**: each case carries
`provenance: retrospective_real_history`, and the `agent-action-v0`
documents were written at case assembly to describe the historical
actions; the attestation in each `case.json` says so.

## Replay it yourself (offline, self-service)

```bash
pip install "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.36.0"

aos-workflow-gate bench-verify --case benchmarks/cases/v0110-incident-counterfactual
aos-workflow-gate verify \
  --input benchmarks/cases/v0110-incident-counterfactual/gate-decision.json \
  --bundle benchmarks/cases/v0110-incident-counterfactual/bundle.json
aos-workflow-gate summarize \
  --input benchmarks/cases/v0110-incident-counterfactual/gate-decision.json
```

Add `--live` to `bench-verify` to also confirm Git ancestry through the
compare API. Interpretation needs no vendor: the record's `reasons`
name each gap, `can_block` states whether anything enforced it, and the
summary renders the same text the GitHub Action posts.

## Boundary

Decision records carry `UNSIGNED_NOT_OFFICIAL` status. A `PASS` here
means the explicit policy was satisfied by the collected signals; a
`BLOCK` means it was not. No security, compliance, or quality claim
about the agent or its changes is made, and this benchmark ranks no
tools and scores no competitors.

## Automated contrast and the adversarial corpus

[`contrast/CONTRAST.md`](contrast/CONTRAST.md) is the standing
GitHub-baseline vs AOS-verdict table, generated by `tools/contrast.py`
from committed evidence only; the suite regenerates it on every CI run
and asserts byte equality, so it cannot drift from the evidence.
Baselines are operator-declared; scope is required status checks, not
full merge-readiness.

[`adversarial/cases/`](adversarial/cases/) is the frozen adversarial
regression corpus: imposter apps, tampered identities, self-promoting
sources, unverified freshness, incomplete collections, zero-required
states, and foreign subjects. Every case replays on every CI run.
Expected verdicts exist only as test assertions over corpus data —
they are never an input to the evaluator, and a test asserts the
evaluator code cannot even name them.
