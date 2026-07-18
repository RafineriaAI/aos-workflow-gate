# Use Cases

These are supported decision patterns, not claims that every repository should
enforce them.

## Use case 1: required-control gap

A maintainer needs one exact-SHA control-assurance decision instead of manually
reconciling branch rules, check runs, workflow runs, commit statuses, and
producer identity.

The gate:

- `BLOCK`s when explicit required evidence is missing, failed, pending,
  stale, malformed, from an unverifiable producer, or bound to another
  subject;
- `WARN`s when the policy declares an advisory gap, including zero enforced
  checks or non-independent verifier evidence;
- `PASS`es when every declared requirement is satisfied.

The record includes the subject, policy and input identities, structured
reason, verifier manifest, `can_block`, and digests. It does not claim full
merge-readiness.

## Use case 2: advisory rollout

A team wants visibility without blocking contributors. The Action runs in
advisory mode, publishes one dominant finding and next action, and uploads the
record, bundle, policy, and static HTML evidence. A `BLOCK` verdict still
returns process success until enforcement is explicit.

Promotion to enforcement follows repeated stable runs, measured noise, owner
agreement, and a tested rollback path.

## Use case 3: context-aware evidence policy

A repository requires evidence that GitHub branch rules do not model directly,
such as an independent verifier when the same PR changes the verifier itself.
AOS represents that condition as a structured signal and lets the repository
policy decide whether it is advisory or required.

The verifier-change mechanism is deterministic and advisory by default. It
does not infer intent, authorship, correctness, or approval.

## Use case 4: agent-action governance

An agent action declaration is validated for canonical digests, repository and
base-SHA binding, subject, freshness, and bounded duplication. The resulting
`source-v0` item is evidence a policy may consume, never execution authority
or semantic approval.

## Use case 5: release decision replay

A release maintainer preserves the decision record, bundle, and policy for the
tagged commit. Another operator can verify digests, disclose verifier mismatch,
render the same diagnosis, and replay the policy offline.

Replay proves consistency with recorded artifacts. It does not prove that the
release was safe or defect-free.
