# CI Integrations

The gate core (`evaluate`, `verify`, `summarize`, `export`) is
platform-neutral: plain Python 3.11+, zero runtime dependencies, JSON in and
out. Any CI system that can run Python can produce and replay decision
records. Platform-specific parts are deliberately thin: the GitHub Action
and the GitHub check-runs collector.

## GitHub Actions

Zero-config and explicit modes are documented in the [README](../README.md).

Required token permissions: a workflow `permissions:` block sets every
unlisted scope to `none`, so declare every read scope used by zero-config:

```yaml
permissions:
  contents: read
  checks: read
  actions: read
  pull-requests: read
  statuses: read
```

- `contents: read` — repository and branch access.
- `checks: read` — check runs and check suites.
- `actions: read` — workflow-run visibility for the exact SHA.
- `pull-requests: read` — PR metadata and the changed-file set.
- `statuses: read` — legacy commit statuses.

Public repositories may allow unauthenticated reads; private repositories
require the declared scopes. Reading classic branch-protection details may
still be unavailable to `GITHUB_TOKEN`; the gate records that surface as
unverifiable instead of interpreting it as unprotected.

Explicit-bundle mode does not call the API and needs only `contents: read`.
No `write` scope of any kind is required; the gate is read-only by design.

## GitHub Enterprise Server

The collector works against GHES out of the box:

- In GHES Actions workflows, the runner's `GITHUB_API_URL` and
  `GITHUB_SERVER_URL` environment variables are used automatically; the
  subject repository is recorded as the full project URL so evidence stays
  unambiguous across hosts.
- The same complete read-only `permissions:` block applies. GHES
  repositories are typically private, so every listed scope is required
  for full zero-config collection.
- Outside workflows, pass `--api-url https://<ghes-host>/api/v3` to
  `collect`.

## GitLab CI (explicit bundle)

A GitLab jobs collector is planned (see [ROADMAP](../ROADMAP.md)); until it
exists, run the platform-neutral core on an explicitly provided bundle:

```yaml
gate:
  image: python:3.12-slim
  script:
    - pip install --quiet "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.33.0"
    - aos-workflow-gate evaluate
        --input signal-bundle.json
        --policy policy.yml
        --out gate-decision.json
    - aos-workflow-gate verify
        --input gate-decision.json --bundle signal-bundle.json
  artifacts:
    paths: [gate-decision.json]
```

Record the bundle's source identity with full URLs (for example
`"repository": "https://gitlab.com/group/project"`); `export` then names the
in-toto subject with that URL verbatim.

## Jenkins or any shell

```bash
python3 -m pip install "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.33.0"
aos-workflow-gate evaluate --input bundle.json --policy policy.yml --out record.json
aos-workflow-gate summarize --input record.json > gate-summary.md
```

Exit codes: advisory mode always exits 0; `--enforce` (or a blocking policy)
exits 1 on `BLOCK`; malformed operator input exits 2.

## Boundary

Only the GitHub check-runs collector is implemented today. On other
platforms the operator supplies the signal bundle, and the record's
integrity properties (digests, replay, tamper evidence) apply from that
point on — collection provenance on those platforms is the operator's
claim, not the gate's.
