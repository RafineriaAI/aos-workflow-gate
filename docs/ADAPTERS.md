# Signal Adapters

Adapters reduce a tool's output to a source in the signal bundle. They are
**mechanical, never judgmental**: a fixed, documented status mapping and a
digest over exactly the identity subset used. Interpretation stays in the
policy — an adapter must never become a hidden authority.

## GitHub check runs (built in)

`collect` reads completed check runs for the exact commit and preserves every
conclusion verbatim. Generated zero-config policies set
`required_status_semantics: github`, so required `success`, `neutral`,
and `skipped` conclusions match GitHub's merge semantics. Explicit policies
may set `required_status_semantics: success-only` to require literal success.
Policies that omit the field retain the historical `success-only` behavior, so
committed replay does not change silently. See
[SECURITY_READINESS.md](SECURITY_READINESS.md) for the data model.

## SARIF 2.1.0 — `--sarif PATH` (repeatable)

Mapping contract:

| Results in the file | Source status |
| --- | --- |
| any `error`-level result | `failure` |
| only `warning`/`note` results (missing level counts as `warning`, the SARIF default) | `warning` |
| no results | `success` |

The source id defaults to `sarif.<tool-name>`; the digest covers
`{tool, version, error_count, warning_count, note_count, status}` per
the identity-completeness invariant
([SOURCE_CONTRACT.md](SOURCE_CONTRACT.md)). The decision uses only those
counts and levels. For fast diagnosis, the reason also names up to three
top `ruleId` values and up to three alphabetically selected affected artifact
paths; the original SARIF remains authoritative for complete findings and
locations.

The Action accepts existing local SARIF files without executing a scanner:

```yaml
- name: Scan GitHub workflows
  run: zizmor --format=sarif . > zizmor.sarif.json
- name: AOS decision
  uses: RafineriaAI/aos-workflow-gate@v0.37.1
  with:
    sarif: zizmor.sarif.json
```

Checkout, scanner installation, and SARIF generation happen in earlier steps.
AOS reads the file on the runner, records its digest-bound summary, and uploads
nothing to RafineriaAI. The
[zizmor integration contract](https://docs.zizmor.sh/integrations/)
states that SARIF mode exits `0` even when findings exist. A green scanner step
therefore does not mean an empty SARIF report; the generated AOS policy exposes
such findings as advisory `WARN`.

## OpenSSF Scorecard — `--scorecard PATH`

Presence-and-integrity signal only: status is `success` when the report
parses; the aggregate score and check count travel in the summary and
digest **as data, not as a verdict**. Score thresholds are a policy-layer
concern and are deliberately not implemented in the adapter.

## External adapters (`source-v0`)

Adapters outside this package emit plain JSON validating against the
versioned [source contract](SOURCE_CONTRACT.md) and enter a bundle via
`aos-workflow-gate import` (file or stdin). The gate never loads
third-party code — no plugin runtime. All adapters, built-in and
external, follow the same identity-completeness invariant: the digest
identity contains the status and every decision-relevant observation.

## Collisions and required flags

Adapter source ids must not collide with collected check-run names (pass
an explicit id if they do). Names listed in `--require` mark adapter
sources required exactly like check runs; the decision record's
required flags are derived from the policy at evaluation time — a
source can never mark itself required.

## Boundary

Adapters do not verify the authenticity of the input files; a SARIF or
Scorecard file is the operator's asserted evidence
(`signal_source: sarif_file` / `scorecard_file` records that provenance).
No scanner-replacement, compliance, or security-audit claim is made.
