# Use Cases

## Use case 1: pull request release gate

A maintainer wants one decision record for a pull request instead of manually reading CI checks, scanner output, dependency updates, and agent comments.

The gate should:

- `BLOCK` when required checks are missing, failed, stale, or ambiguous.
- `WARN` when required checks pass but advisory evidence contains known risks.
- `PASS` when required evidence is present and policy requirements are satisfied.

The result should include the reason, policy identity, input identities, and verification status.

## Use case 2: advisory rollout

A team wants to evaluate the gate without blocking contributors.

The gate should run in advisory mode, publish a summary, and collect decision artifacts. Only after repeated stable behavior should the team make `BLOCK` enforceable.

## Use case 3: AI-agent review governance

A repository uses AI-agent review comments. The gate should not treat an agent comment as authority by itself. It should treat the agent result as one signal with provenance, severity, and policy role.

For example:

- Agent found no issue: informational signal.
- Agent found a release-blocking policy violation: possible `BLOCK` only if the policy says that source is authoritative for that rule.
- Agent output is malformed or missing: `WARN` or `BLOCK` depending on policy.

## Use case 4: release candidate replay

A release manager wants to explain why a release candidate was allowed or blocked.

The gate should preserve enough evidence to replay the same decision from the same input bundle and policy. Replayability is more important than a broad claim that the release is safe.
