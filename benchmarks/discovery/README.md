# Evidence-led pain discovery corpus

A frozen, reproducible corpus of real merged pull requests from public
repositories, built to test whether the pains this gate claims to
address actually occur — before any policy ships. Method first, verdict
second: candidate policies are assessed against the **discovery** split
only; the **holdout** split stays untouched until a policy is frozen,
so a policy can never be tuned on the data that later validates it.

## Boundary — read this first

Public metadata only: changed file paths, counts, timestamps, check
conclusions, and workflow paths. **No code, no diffs, no review-comment
bodies are stored** (review comments are reduced to counts and a
CI-keyword flag at capture time), and nothing from the observed
repositories is executed. This corpus is a sample, not a study: it
supports frequency statements about itself, not claims about GitHub at
large, and it ranks no tools and scores no repositories.

## Contents

- [`manifest.json`](manifest.json) — the frozen membership: repository,
  PR number, merge date, capture time, and the deterministic split
  (`sha256("<repo>#<number>")`, last hex digit `c`–`f` ⇒ holdout,
  ~25%). The split is recomputable by anyone from the rule; the
  manifest freezes the sample itself.
- [`analysis.json`](analysis.json) — per-PR mechanical facts (path
  classes, review-comment counts, chronology, check-run conclusions,
  workflow-run paths) and the candidate-policy summary computed from
  the discovery split.
- [`../../tools/discovery.py`](../../tools/discovery.py) — the builder.
  Maintainer-run; CI never touches the network. Re-running it produces
  a *new* corpus (a new capture), never a mutation of this one.

## Sample

90 merged pull requests captured 2026-07-11: the 30 most recently
created merged PRs each from `apache/airflow`, `celery/celery`, and
`RafineriaAI/aos-workflow-gate` (the dogfooding slice — vendor history,
stated as such). Split: 70 discovery / 20 holdout.

## Candidate policy 1: verifier-change independence

**Definition.** A merged PR changes its own verification mechanism —
a workflow file, the test harness, or scanner configuration. Evidence
produced solely by the changed mechanism is not independent: the PR
grades itself with the grader it just edited.

**Findings (discovery split, n=70):**

- **Frequency:** 27 of 70 PRs (≈39%) touch a verifier surface.
- **Positive cases with mechanically self-validating runs:** 6 PRs
  whose head commit's workflow runs include a workflow file changed by
  the same PR — across all three repositories (`apache/airflow`,
  `celery/celery`, and this repository's own history; the concrete
  list is in `analysis.json` under
  `candidate_policies.verifier_change_independence`).
- **Negative controls:** 43 discovery PRs never fire the policy
  (10 itemized in `analysis.json`, total recorded).
- **Noise assessment:** routine dependency bumps (bot-authored,
  pin-files-only) are the planned mechanical exclusion. In this sample
  the exclusion fired **zero** times — a kept negative result: the
  sampled bot PRs also touched non-pin files, so the exclusion must
  not be assumed to carry the noise burden by itself.

**Reading:** the pain is frequent enough to matter and mechanical
enough to detect without any model in the loop. Advisory-first is
justified: 39% firing at BLOCK severity would be unusable noise; the
6 self-validating cases are the sharp subset worth surfacing loudly.

## Candidate policy 2: green-but-not-exercised

**Definition.** A merged PR whose head commit carries `skipped` or
`neutral` check conclusions and no failure: the dashboard reads green
while some declared evidence never ran.

**Findings (discovery split, n=70):**

- **Frequency:** 39 of 70 PRs (≈56%).
- **Negative controls:** recorded in `analysis.json` with totals.
- **Noise assessment:** skipped conclusions are often *intentional*
  (path filters, conditional jobs). At this frequency the signal is
  advisory visibility by definition, never a defect claim — a policy
  that blocked on it would be wrong more often than right.

## Negative results, kept deliberately

- `negative_results.unretrievable_streams` is empty for this capture:
  every sampled PR still served its check runs and workflow runs. That
  is itself a datum about evidence durability for *recent* PRs — it
  says nothing about older history, where GitHub retention limits are
  known to apply (see the v0.11.0 benchmark case, which relies on
  persisted check runs from months past).
- The routine-bump exclusion never fired (see above).
- Nothing in this corpus was pruned for being unfavorable; the
  green-but-not-exercised rate on the vendor's own repository is
  recorded like everyone else's.

## Relation to the other benchmarks

The [real-agent governance benchmark](../README.md) records replayable
*cases*; this corpus records *frequencies* that justify which cases
are worth building. The holdout split is reserved for validating the
frozen verifier-change policy (see the trusted verifier-change work)
against data it was not tuned on.

No production, compliance, or security-audit claim is made. Decision
records referenced here carry `UNSIGNED_NOT_OFFICIAL` status.
