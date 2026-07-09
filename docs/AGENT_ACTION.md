# Agent Action Adapter (`agent-action-v0`)

An *agent action document* is agent-agnostic evidence of what an agent
intends to do or has done: repository, base commit, subject, declared
intent, action type, and parameters. The `agent-action` command
validates such documents and reduces each to a
[`source-v0`](SOURCE_CONTRACT.md) source whose status is the validation
state — evidence a policy can require, never an approval.

```bash
# validate and pipe into a bundle
aos-workflow-gate agent-action --input action.json \
  | aos-workflow-gate import --source - \
      --repository OWNER/REPO --sha <subject-sha> --out bundle.json

# or bind against an existing bundle and merge in one step
aos-workflow-gate agent-action --input action.json \
  --bundle bundle.json --live --branch main --out bundle.json
```

## Document contract

| Field | Required | Meaning |
| --- | --- | --- |
| `contract` | yes | `agent-action-v0`. |
| `repository` | yes | Where the action applies. |
| `base_sha` | yes | The commit state the agent started from (40-hex). |
| `subject` | yes | `{repository, sha}` the produced evidence is about — binds the action to the gate subject. |
| `intent` | yes | Mapping with at least `task`: what the agent was asked to do. |
| `action` | yes | `{type, parameters}`: what it did or proposes. |
| `snapshot` | no | Pinned observations of the base state (e.g. `{"branch": "main"}`). |
| `digests` | no | Claimed canonical digests (`intent`, `action`, `parameters`, `snapshot`); verified against recomputation. |
| `agent` | no | Provenance data (name, version) — data, not identity. |

Canonical digests bind everything: the `action` digest covers the type,
the parameters digest, the intent digest, the repository, the base
commit, and the subject — an identical action replayed against the same
base state yields the same digest.

## Validation states

Structural validation failures (missing fields, malformed SHAs, a
subject repository different from the document repository —
cross-repository and fork flows are out of scope for v0) are hard,
path-addressed errors. A structurally sound document is classified into
exactly one state, with precedence **integrity, then binding, then
freshness failure, then duplication, then unknown freshness**:

| State | Source status | Meaning |
| --- | --- | --- |
| `valid` | `success` | Intact, bound, verified fresh under the chosen mode, not duplicated in scope. |
| `tampered` | `tampered` | A claimed digest does not match the recomputed canonical digest. |
| `subject_mismatch` | `subject_mismatch` | The document's subject does not match the bundle's subject. |
| `stale` | `stale` | `base_sha` is not the observed head (live or pinned check): the action was prepared against a state that has moved. |
| `bounded_duplicate` | `bounded_duplicate` | Same action digest already seen within this bundle or invocation. |
| `freshness_unverified` | `freshness_unverified` | No live or pinned base was provided, so staleness was not evaluated — `valid` is not claimed, and required sources fail closed. |

`valid` maps to `success` — a fixed mechanical mapping (like the SARIF
level mapping), so a policy can *require* a valid agent action. Every
other state fails closed for required sources and warns for advisory
ones. Each source's summary carries the state-specific explanation.

## Live-state or pinned-snapshot validation

- `--live --branch NAME` compares `base_sha` to the branch's current
  head via the API (one budgeted call per repository/branch).
- `--pinned-base SHA` compares against an operator-pinned base — fully
  offline and reproducible.
- With neither, staleness is **not evaluated** and the state is
  `freshness_unverified` — the status itself carries the limitation, so
  nothing is silently assumed fresh and a required agent action cannot
  pass without a freshness mode.

## Boundaries

- **No execution authority.** The adapter validates a description of an
  action; it never executes, applies, or reverts anything.
- **No semantic approval claim.** `success` asserts structural
  integrity and binding only. Whether the change is good, safe, or
  wanted is not stated and cannot be derived from this source.
- **No global duplicate or replay protection.** Duplicate detection is
  bounded to the bundle or invocation at hand, and the source summary
  states that boundary. Cross-bundle replay protection would require
  infrastructure this adapter does not have and does not claim.
- **Validation–policy separation.** The adapter reports states; the
  policy decides what any state means for the verdict.
