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
`{tool, version, error_count, warning_count, note_count}`; the counts are
repeated in the human summary. The gate does not read rules, locations, or
severities beyond the level — scanners keep their own report as the
authority on findings.

## OpenSSF Scorecard — `--scorecard PATH`

Presence-and-integrity signal only: status is `success` when the report
parses; the aggregate score and check count travel in the summary and
digest **as data, not as a verdict**. Score thresholds are a policy-layer
concern and are deliberately not implemented in the adapter.

## Collisions and required flags

Adapter source ids must not collide with collected check-run names (pass
an explicit id if they do). Names listed in `--require` mark adapter
sources required exactly like check runs.

## Boundary

Adapters do not verify the authenticity of the input files; a SARIF or
Scorecard file is the operator's asserted evidence
(`signal_source: sarif_file` / `scorecard_file` records that provenance).
No scanner-replacement, compliance, or security-audit claim is made.
