# Executable Change Proof

Status: experimental local plug-in included in `v0.38.0`. It is not enabled by
the default GitHub Action and is not evidence of external product-market fit.

`prove-change` answers one concrete code-review question:

> The tests pass, but would they still pass without the implementation change?

AOS is an add-on to an existing targeted test command, not a replacement for a
test runner, coverage service, scanner, or reviewer. It does not ask an LLM for
a verdict. It runs the supplied verifier at exact `HEAD`, removes selected
implementation changes in disposable Git worktrees while retaining the PR's
tests, and runs the same verifier again.

## Product role and calibrated scope

Run Change Proof when a pull request changes implementation and tests, or when
an operator explicitly states that the verifier should observe a behavior
change. Skip it by default for formatting, documentation, behavior-preserving
refactors, and performance-only changes unless the supplied verifier measures
the intended effect.

Use a fast targeted command. AOS runs one `HEAD` check and two challenge checks.
It should be inserted after ordinary tests in CI or an agent workflow, not used
as a separate quality system.

The motivation is measurable but does not prove AOS value: a 2026
[study of 4,882 agent-generated pull requests](https://arxiv.org/abs/2607.18057)
found that agents changed tests in 49.6% of code-changing PRs, while only
22.5% of Python code-and-test PRs improved coverage. Coverage and Change Proof
answer different questions; this evidence
only supports testing the product hypothesis.

## First run

Run this from a clean clone with the project's test dependencies available:

```bash
python -m aos_workflow_gate prove-change \
  --base origin/main \
  --repository OWNER/REPO \
  -- \
  python -m pytest
```

The default path classifier selects changed implementation files with common
code suffixes and excludes conventional test, documentation, example, fixture,
benchmark, and vendor paths. Narrow the experiment when required:

```bash
python -m aos_workflow_gate prove-change \
  --base origin/main \
  --source "src/**" \
  --exclude "src/generated/**" \
  -- \
  npm test -- --runInBand
```

`--source` and `--exclude` are repeatable Git-style path globs. At most 200
implementation paths enter one v0 experiment.

## Decision semantics

| Observation | Verdict | Meaning |
| --- | --- | --- |
| Verifier passes at `HEAD`; two clean challenge runs fail with the same exit code | `PASS` | The supplied checks are sensitive to removal of the selected implementation change. |
| Verifier passes at `HEAD`; two clean challenge runs also pass | `WARN` | The supplied checks do not distinguish the selected implementation change from the base. |
| Two clean `HEAD` runs fail with the same exit code | `BLOCK` | The explicit verifier command has a reproducible failure on this exact commit. |
| Timeout, launch error, patch error, or unstable repeat | `WARN` | The experiment is inconclusive; no confirmed result is inferred. |

Advisory mode is the default, so a `BLOCK` verdict still exits `0`. With
`--mode enforce`, only `BLOCK` exits `1`. Operational input errors exit `2` and
produce no verdict.

A `PASS` is deliberately bounded. A failing challenge can result from a build,
import, type, or test failure. It proves change sensitivity, not that the new
behavior is correct, complete, secure, or aligned with product intent.

## Evidence

The command writes:

```text
.aos-proof/
|- change-proof-source.json
|- bundle.json
|- policy.json
`- gate-decision.json
```

The `source-v0` identity binds:

- repository, exact head, supplied base, and effective merge-base SHAs;
- explicit verifier argv and its digest;
- selected implementation paths and patch digest;
- each run's state, exit code, elapsed milliseconds, output byte counts, and
  stdout/stderr digests;
- final mechanical status.

Raw command output is not written to evidence. Verify and replay the decision
projection with the existing surfaces:

```bash
aos-workflow-gate verify \
  --input .aos-proof/gate-decision.json \
  --bundle .aos-proof/bundle.json

aos-workflow-gate summarize \
  --input .aos-proof/gate-decision.json \
  --bundle .aos-proof/bundle.json \
  --policy .aos-proof/policy.json
```

Offline replay confirms the recorded decision from the recorded evidence. A
fresh semantic reproduction requires the referenced commits, dependencies,
and verifier command to remain available.

## Execution boundary

- The command after `--` is supplied by the operator and executed as argv with
  `shell=False`. AOS never reads a command from PR text or repository config.
- Every run uses a disposable detached Git worktree. The source worktree is
  not patched. Temporary worktrees are removed and pruned after each run.
- The verifier inherits the operator environment and can execute arbitrary
  project code, access the network, or mutate external systems. Use a sandboxed
  CI job and a side-effect-free test command.
- Command arguments are evidence. Never place credentials or secrets in argv;
  use appropriately scoped environment variables when the verifier needs them.
- AOS stores output digests and byte counts, not raw stdout or stderr. The
  verifier itself may still transmit data; its behavior is outside AOS.
- Do not expose privileged secrets to untrusted fork code. This experiment is
  opt-in and intentionally absent from the read-only zero-config Action.

## Known limitations

- v0 removes selected files as one implementation patch; it does not isolate
  individual functions or mutations.
- Tests colocated inside implementation files are reverted with those files
  unless paths are selected more narrowly.
- Local dependency directories are not copied into disposable worktrees.
  Prefer environment-level dependencies or a verifier that provisions its own
  isolated environment.
- Stateful, timing-sensitive, or flaky checks can remain inconclusive despite
  the two-run confirmation rule.
- The experiment does not infer requirements from tickets, documentation, or
  business rules and does not generate adversarial tests yet.

## Current benchmark and advancement gate

The exploratory plug-in benchmark covers eight exact-SHA cases from five
public repositories. The mechanism and replay passed in 8/8 cases. Tests
distinguished the implementation in 5/5 real code-and-test PRs. A controlled
under-scoped verifier produced the expected warning. Raw Change Proof also
warned for 2/2 behavior-preserving or performance changes, showing why
eligibility must be calibrated. Median CLI time was 7.008 seconds and median
verifier work was 3.157 times one `HEAD` run in this small, fast sample.

These are mechanism observations. There were no external accepted warnings,
decision changes, retained installations, or ROI observations. See the
[generated report](../benchmarks/change-proof-plugin/REPORT.md).

Do not enable the feature by default or define a paid offer until external use
meets all of these conditions:

1. at least 50 eligible PRs across at least five independent repositories;
2. at least 50% of warnings lead to an accepted verifier improvement;
3. irrelevant or wrong warnings and inconclusive runs are each at most 10%;
4. median added wall time is below two minutes for the targeted verifier;
5. setup takes at most ten minutes in at least 80% of repositories;
6. at least 20% of accepted warnings change merge readiness or catch a weak
   test before review;
7. at least half of trial repositories retain the plug-in after four weeks.
