# Real-Agent Benchmark Harness (`benchmark-case-v0`)

A benchmark case is a directory of **recorded** artifacts from a real
agent run: a predeclared task with acceptance criteria and budget, the
declared base state, the agent's [`agent-action-v0`](AGENT_ACTION.md)
document, the produced patch, and the gate's bundle/policy/decision
triple. `bench-verify` validates the case and replays the decision —
**it runs nothing**: no agent, no patch application, no command
execution of any kind (Git ancestry uses the compare API or is reported
unverifiable; the harness never shells out).

```bash
aos-workflow-gate bench-verify --case benchmarks/cases/<case-id> [--live] [--json]
```

## Case format

`case.json` inside the case directory:

| Field | Meaning |
| --- | --- |
| `contract` | `benchmark-case-v0`. |
| `case_id` | Stable case name. |
| `task.description` | The task, **predeclared** before the agent ran. |
| `acceptance_criteria` | Predeclared list — written before the run, not after the fact. |
| `budget` | Predeclared limits (e.g. wall-clock minutes, agent turns). |
| `base_state` | `{repository, base_sha, branch}` the agent started from. |
| `artifacts` | Relative file names: `action`, `patch`, `bundle`, `policy`, `record` (must stay inside the case directory). |
| `bindings` | `action_digest`, `patch_digest`, `record_digest` — the digest spine tying action, patch, and decision together. |
| `chronology` | Declared `task_declared` / `action_captured` / `decision_evaluated` timestamps. |
| `attestation` | Operator prose stating how the artifacts were captured. |

## Checks and the verified vs unverifiable boundary

Every check reports `ok`, `failed`, or `unverifiable`. Failed checks
fail the run (exit 1); unverifiable checks never do — they are
disclosure, and hiding them would be the actual failure.

**Mechanically verified (`ok`/`failed`):**

- `artifact_presence` — every declared artifact file exists.
- `chronology_consistent` — declared timestamps strictly increase in
  the order task → action → decision.
- `action_document` and `action_digest_binding` — the action validates
  against `agent-action-v0` and recomputes to the bound digest.
- `action_base_binding` — the action is bound to the declared base
  state.
- `patch_digest_binding` — the patch bytes match the declared digest.
- `record_integrity` and `offline_replay` — the decision record
  self-verifies, is bound to the case, and replays against the
  committed bundle with no network.
- `policy_binding` — the shipped policy artifact digests to the
  record's policy digest: the case cannot ship a different policy than
  the decision used.
- `semantic_replay` — **true offline semantic replay**: the committed
  bundle and policy are re-evaluated and the derived verdict, reasons,
  inputs, and subject must equal the committed record (the generator
  version is deliberately excluded so records replay across releases).
- `subject_binding` — the decision subject equals the action's
  declared subject.
- `git_ancestry` (with `--live`) — the compare API confirms the subject
  descends from the declared base; offline it is unverifiable, never
  assumed.

**Explicitly unverifiable — stated, not glossed over:**

- `chronology_truth` — timestamps are operator-declared; their truth
  rests on the attestation, not on cryptography.
- `patch_authorship` — **no patch-authorship claim**: the harness
  verifies bytes against the binding, never who or what produced them.
- `github_baseline` — when a case declares a GitHub baseline
  (merge-ready state), it is operator-declared from historical platform
  state and not mechanically re-verifiable offline.
- `operator_attestation` — recorded prose; **no cryptographic
  authorship claim** is made or implied.

## Exit codes

| Exit | Meaning |
| --- | --- |
| 0 | No check failed (unverifiable checks may be present and are listed). |
| 1 | At least one mechanical check failed. |
| 2 | The case itself is malformed or the run could not complete. |

## Boundary

The harness validates recorded artifacts and replays decisions. It
executes **no arbitrary command execution** path — there is no code
path that runs a case-provided program, script, or patch. A case
passing `bench-verify` means the recorded evidence is internally
consistent and replayable; it does not mean the agent's change was
good, safe, or approved.
