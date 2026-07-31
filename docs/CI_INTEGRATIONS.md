# CI Integrations

The gate core (`evaluate`, `verify`, `summarize`, `export`) is
platform-neutral: plain Python 3.11+, zero runtime dependencies, JSON in and
out. Any CI system that can run Python can produce and replay decision
records. Native online collection is GitHub-specific: the Action and CLI read
rulesets or classic protection, check runs and suites, workflow runs, pull
request metadata, and commit statuses. Other platforms use explicit bundles
or external `source-v0` adapters.

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
The default gate is read-only by design and requires no write scope.

### Optional published decision check

Set `publish-check: "true"` to publish a separate
`AOS Workflow Gate / merge readiness` check. This opt-in path needs
`checks: write` instead of `checks: read`:

```yaml
permissions:
  contents: read
  checks: write
  actions: read
  pull-requests: read
  statuses: read

steps:
  - uses: RafineriaAI/aos-workflow-gate@v0.38.0
    with:
      publish-check: "true"
      published-check-mode: advisory
```

`published-check-mode: advisory` maps `WARN` and `BLOCK` to a neutral GitHub
conclusion. `published-check-mode: required` maps them to failure; configure
the stable check name as required in a ruleset or Branch Protection for that
failure to block merge. This setting does not change the AOS verdict or
Action exit code. Action `mode: enforce` remains the separate process-exit
control.

AOS reserves the stable decision-check context during requirement discovery,
records that self-reference as evidence, and publishes one completed check
only after the decision record exists. It therefore neither grades itself nor
leaves a custom `in_progress` check behind when the job is cancelled. The
check contains only the diagnosis, exact commit identity, record digest, and
workflow-run link. No source code is uploaded.

For pull requests from forks, GitHub can downgrade `GITHUB_TOKEN` to read-only.
If publication then fails, advisory mode keeps the decision record and reports
a degraded output; required mode exits 2 because the blocking check was not
published. Do not switch to `pull_request_target` merely to regain write access
for untrusted code.

The optional Action input `sarif` accepts newline-separated paths generated
by earlier scanner steps. AOS does not install or execute the scanner. The
decision reason includes bounded rule/path context while the original SARIF
remains the finding authority; see [Signal adapters](ADAPTERS.md).

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
    - pip install --quiet "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.38.0"
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
python3 -m pip install "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.38.0"
aos-workflow-gate evaluate --input bundle.json --policy policy.yml --out record.json
aos-workflow-gate summarize --input record.json > gate-summary.md
```

Exit codes: advisory mode always exits 0; `--enforce` (or a blocking policy)
exits 1 on `BLOCK`; malformed operator input exits 2.

## Boundary

Only GitHub has a built-in online collector. On other platforms the operator
supplies the signal bundle or imported `source-v0` evidence. Record integrity
properties (digests, replay, tamper evidence) apply after that boundary;
collection provenance and completeness on those platforms remain the
operator's claim, not the gate's.
