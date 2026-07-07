# Policy Packs

Starter policies under `policies/packs/`. Packs are plain, inspectable
policy files — copy one, rename the `policy_id`, and edit the source ids
to match your check names (`ci` is a placeholder). Nothing is hidden: a
pack is exactly what `evaluate --policy` reads.

| Pack | Mode | Requires | Advisory | Intended for |
| --- | --- | --- | --- | --- |
| `minimal-pr-gate` | advisory | `ci` | `scanner.sarif`, `agent.review` | first PR gate; evidence before enforcement |
| `release-candidate` | **blocking** | `ci`, `scanner.sarif` | `agent.review`, `scorecard` | release gates where a missing scan must block |
| `agent-review-advisory` | advisory | `ci`, `agent.review` | `scanner.sarif`, `scorecard` | AI-agent changes: agent review must have run |

The GitHub Action selects a pack by name (see the README); the CLI takes
the file path directly. `release-candidate` is `mode: blocking`, so a
`BLOCK` verdict fails the process even without `--enforce`.

Boundary: packs encode structure, not judgment about your tools; a pack
passing does not make a repository secure, compliant, or release-worthy.
