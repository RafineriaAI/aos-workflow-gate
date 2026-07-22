# Executable Change Proof

Status: experimental local product slice. It is not enabled by the default
GitHub Action, is a `0.38.0` candidate not present in published `v0.37.1`,
and is not evidence of external product-market fit. Test it from a source
checkout until an immutable release explicitly includes it.

`prove-change` answers one concrete code-review question:

> Do the supplied checks distinguish the implementation in this commit from
> the implementation at its merge base?

It does not ask an LLM for a verdict. It runs an explicit verifier command at
the exact `HEAD`, removes the selected implementation changes in a disposable
Git worktree while retaining the PR's tests, and runs the same command again.

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

## Validation target

The feature should advance beyond experimental status only if external use
shows that `change_not_distinguished` findings are accepted, cause stronger
tests or changed merge decisions, add findings beyond ordinary CI and mutation
tools, and remain low-noise at acceptable runtime cost. Internal fixtures prove
mechanics only.
