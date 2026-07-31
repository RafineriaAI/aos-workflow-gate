# Policy Packs

Starter policies shipped inside the package (`aos_workflow_gate/packs/`), so `--policy-pack NAME` works from any install. Packs are plain, inspectable
policy files — copy one, rename the `policy_id`, and edit the source ids
to match your check names (`ci` is a placeholder). Nothing is hidden: a
pack is exactly what `evaluate --policy` reads.

## Accepted risks

A known low-impact `WARN` can be accepted in the repository policy without
deleting its evidence:

```yaml
accepted_risks:
  advisory_warning@scanner.sarif: "Known exception reviewed by the team"
```

The selector is exact: `<rule>@<source-id>`. For a decision-level reason with
no source, use `<rule>@<decision>`. Quote the selector when a source id
contains `:`. The targeted rule must be declared as
`WARN`; wildcard selectors, `BLOCK` rules, and `malformed_input` are
rejected. A match changes
only that reason's effective severity to `PASS`. The record still contains the
original `WARN` severity, selector, justification, policy digest, and accepted
risk count, so replay and review remain possible.

Keep the exception in version control, use a concrete justification, and
remove it when the assumption stops being true. This is explicit
policy-as-code, not model training or an invisible per-user preference.

| Pack | Mode | Requires | Advisory | Intended for |
| --- | --- | --- | --- | --- |
| `minimal-pr-gate` | advisory | `ci` | `scanner.sarif`, `agent.review` | first PR gate; evidence before enforcement |
| `release-candidate` | **blocking** | `ci`, `scanner.sarif` | `agent.review`, `scorecard` | release gates where a missing scan must block |
| `agent-review-advisory` | advisory | `ci`, `agent.review` | `scanner.sarif`, `scorecard` | AI-agent changes: agent review must have run |
| `evidence-integrity` | **blocking** | `ci` | — | blocks on evidence-integrity conditions branch protection cannot express: incomplete collection and non-independent evidence (the change judges itself) |
| `code-change-proof` | advisory | `code.change-proof` | - | internal policy used by experimental `prove-change`: stable HEAD failure blocks, insensitive or inconclusive experiment warns |

Both the CLI (`run --policy-pack NAME`) and the GitHub Action can select a
pack by name; `evaluate --policy` takes any file path directly. Pack source
IDs are literal. Action selection is useful only when repository check IDs
match the pack; otherwise copy the pack, edit its IDs, and pass it through
`policy`. `release-candidate` is `mode: blocking`, so a `BLOCK` verdict
fails the process even without `--enforce`.

`code-change-proof` is resolved automatically by `prove-change`; it is not a
GitHub check-name starter pack and is intentionally absent from the default
Action. See [Executable Change Proof](CHANGE_PROOF.md).

Boundary: packs encode structure, not judgment about your tools; a pack
passing does not make a repository secure, compliant, or release-worthy.
