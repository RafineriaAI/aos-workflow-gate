# Signal Adapters

Adapters reduce a tool's output to a source in the signal bundle. They are
**mechanical, never judgmental**: a fixed, documented status mapping and a
digest over exactly the identity subset used. Interpretation stays in the
policy — an adapter must never become a hidden authority.

## GitHub check runs (built in)

`collect` reads the commit's completed check runs; conclusions are
preserved verbatim and only `success` passes downstream. See
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
([SOURCE_CONTRACT.md](SOURCE_CONTRACT.md)); the counts are
repeated in the human summary. The gate does not read rules, locations, or
severities beyond the level — scanners keep their own report as the
authority on findings.

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
