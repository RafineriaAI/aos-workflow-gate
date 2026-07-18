# Policy Packs

Starter policies shipped inside the package (`aos_workflow_gate/packs/`), so `--policy-pack NAME` works from any install. Packs are plain, inspectable
policy files — copy one, rename the `policy_id`, and edit the source ids
to match your check names (`ci` is a placeholder). Nothing is hidden: a
pack is exactly what `evaluate --policy` reads.

| Pack | Mode | Requires | Advisory | Intended for |
| --- | --- | --- | --- | --- |
| `minimal-pr-gate` | advisory | `ci` | `scanner.sarif`, `agent.review` | first PR gate; evidence before enforcement |
| `release-candidate` | **blocking** | `ci`, `scanner.sarif` | `agent.review`, `scorecard` | release gates where a missing scan must block |
| `agent-review-advisory` | advisory | `ci`, `agent.review` | `scanner.sarif`, `scorecard` | AI-agent changes: agent review must have run |
| `evidence-integrity` | **blocking** | `ci` | — | blocks on evidence-integrity conditions branch protection cannot express: incomplete collection and non-independent evidence (the change judges itself) |

Both the CLI (`run --policy-pack NAME`) and the GitHub Action can select a
pack by name; `evaluate --policy` takes any file path directly. Pack source
IDs are literal. Action selection is useful only when repository check IDs
match the pack; otherwise copy the pack, edit its IDs, and pass it through
`policy`. `release-candidate` is `mode: blocking`, so a `BLOCK` verdict
fails the process even without `--enforce`.

Boundary: packs encode structure, not judgment about your tools; a pack
passing does not make a repository secure, compliant, or release-worthy.
