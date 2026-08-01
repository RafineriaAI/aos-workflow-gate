# Should your team keep AOS?

AOS is a free add-on to existing tests and GitHub checks. It has two narrow
jobs:

1. explain whether expected GitHub controls ran for the exact commit;
2. experimentally check whether a targeted verifier notices removal of the
   actual implementation patch.

It does not decide whether the code is correct. It does not replace a reviewer,
a test suite, coverage, mutation testing, or a security scanner.

## Use it when

AOS is a reasonable experiment when at least one of these is true:

- reviewers often ask whether a required workflow actually ran;
- fork pull requests or conditional workflows make GitHub status hard to read;
- required checks have stale names or are produced by more than one app;
- a pull request can change the same workflow that judges it;
- code and tests changed together and a reviewer wants bounded evidence that
  the tests notice the implementation;
- you need to keep a readable record for one exact commit.

## Skip it when

AOS is unlikely to help when:

- you want code-quality or architecture feedback;
- the proposed Change Proof run is a behavior-preserving refactor or
  performance-only change with no relevant performance verifier;
- the repository has no meaningful GitHub merge rules;
- the team already understands every failed or missing check immediately;
- nobody will act on the result or keep the saved report.

Removing a tool that adds no new action is the correct outcome.

## Ten-minute trial

1. Install AOS.
2. Run it on five representative pull requests.
3. For every `WARN` or `BLOCK`, ask:
   - Did AOS show something GitHub did not?
   - Is the next step specific and worth doing?
   - Would a maintainer change a decision or take an extra action?
4. Keep the Action in advisory mode.
5. Remove it if the answers remain no.

Check a public pull request without changing it:

```bash
python -m pip install "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.38.0"
aos-workflow-gate check-pr https://github.com/OWNER/REPO/pull/NUMBER
```

## Try Change Proof as a plug-in

Use a fast targeted verifier on a PR that changes implementation and tests:

```bash
aos-workflow-gate prove-change \
  --base origin/main \
  --repository OWNER/REPO \
  -- \
  python -m pytest tests/changed_area -q
```

Keep it only if a `WARN` causes a justified test improvement or merge decision.
Do not count a `PASS` alone as saved money, and do not run it indiscriminately
on refactors or performance work. The verifier runs three times.

## What counts as value?

Count a result as useful only when it does one of these:

- **New action:** identifies a necessary action that GitHub did not already
  make visible.
- **Useful explanation:** turns a confusing GitHub state into a clear cause and
  a concrete next step.
- **Time saved:** replaces manual checking that a maintainer would otherwise
  perform.

Do not count these as value:

- a different label with no different action;
- repeating a red or pending check already obvious in GitHub;
- a correct but low-impact setup observation;
- saved JSON that nobody needs or reads;
- `PASS` without a meaningful rule to satisfy.

## Current evidence

The mechanism is reliable in the committed benchmark: exact-commit binding,
file integrity, and replay passed for every case.

The GitHub-gate result is weak. In the 10-case review-rich holdout AOS added no
new action matching a material human-review problem, explained one existing
GitHub state, and missed all six material code, data, or runtime problems found
by people.

The separate Change Proof experiment passed mechanism checks in 8/8 cases from
five repositories. Five code-and-test PRs were distinguished, one controlled
under-scoped verifier warned, and two behavior-preserving changes showed that
uncalibrated default warnings would be noise. No external action or decision
change was observed.

Therefore continue only the narrow plug-in experiment, keep the GitHub gate
narrow, and do not position AOS as general code review or a paid product. See
[Change Proof](../benchmarks/change-proof-plugin/REPORT.md) and
[Should AOS continue?](../benchmarks/adaptive-value-calibration/REPORT.md).

## Start simple

The first GitHub run needs no policy file. AOS reads active GitHub requirements.

Add configuration only after a repeated problem is clear:

1. Start in advisory mode.
2. Record useful, ignored, and wrong warnings.
3. Add one explicit rule for one recurring problem.
4. Keep a written exception for a known accepted risk.
5. Enable blocking only after the team agrees on rollback and ownership.

## Decide after real use

A team should keep AOS only when, after several weeks:

- people act on a meaningful share of its recommendations;
- it changes at least some merge decisions or avoids manual investigation;
- ignored warnings stay low;
- the same users continue to rely on it;
- the saved report is used for review, release, or audit work.

These measures require real users. Public-repository analysis cannot replace
them.

## Technical terms, translated

- **Required check:** a GitHub check that must pass before merge.
- **Advisory:** AOS reports a problem but does not stop the job.
- **Enforcement:** a non-PASS result can stop the job.
- **Replay:** run the saved inputs again and confirm the same result.
- **Policy:** the small set of rules that says which checks matter.
- **Evidence record:** the saved files showing what AOS read and decided.

You do not need these terms for the first run.

## Next documents

- First-run questions: [User FAQ](USER_FAQ.md)
- GitHub permissions and setup: [CI Integrations](CI_INTEGRATIONS.md)
- Optional rules: [Policy Packs](POLICY_PACKS.md)
- Data and trust boundaries: [Trust](TRUST.md)
- Exact product limits: [Scope](SCOPE.md)
- Contributing: [Contributing](../CONTRIBUTING.md)
