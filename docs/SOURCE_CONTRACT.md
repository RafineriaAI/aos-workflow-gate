# Source Contract v0 (`source-v0`)

The versioned contract for signal sources produced **outside** this
package. Third-party adapters — scanners, scripts, agent tooling —
emit plain JSON that validates against `source-v0` and enters a bundle
via `aos-workflow-gate import`. The gate never loads third-party code:
**no plugin runtime** exists or is planned; an external adapter is a
separate process whose only interface is this JSON contract.

This page has two audiences. **Operators** run `import` and own the
policy. **Integrators** write adapters that emit compliant sources.

## For operators

```bash
# merge external sources into an existing bundle
aos-workflow-gate import --input bundle.json \
  --source my-scanner-source.json --out bundle.json

# or build a fresh bundle from stdin
my-adapter | aos-workflow-gate import --source - \
  --repository OWNER/REPO --sha <commit> --out bundle.json
```

Validation is strict and errors are path-addressed
(`my-source.json[2].digest: must match sha256:<64 lowercase hex>`), so
a broken adapter is caught at import time, not at decision time.
Imported source ids are recorded in the bundle's
`collection.imported_sources`.

Whether an imported source is required or advisory is **your policy's
decision**: list its id under `required_sources` or `advisory_sources`.
The source itself cannot ask to be required.

## For integrators

A `source-v0` source is a JSON object:

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable, unique name; the policy references it verbatim. |
| `kind` | yes | Your adapter's type label (e.g. `sarif_summary`). |
| `status` | yes | **Adapter-defined, non-enum**: any non-empty string. Exactly `success` passes downstream; every other value is preserved verbatim and interpreted by the policy. A status is an observation, never a verdict. |
| `digest` | yes | `sha256:<64 lowercase hex>` over the canonical JSON of your identity object — see the invariant and the normative canonicalization below. |
| `identity` | no (recommended) | The identity object itself. When present, the gate **recomputes the digest and verifies it**, and checks that `identity.status` equals the source `status` — in both `import` (hard error) and `evaluate` (fails closed as malformed input), through one shared validation path. Without it the digest is an opaque commitment only you can check. |
| `contract` | no | `source-v0` (assumed when absent; anything else is rejected). |
| `summary` | no | One human sentence. |
| `signal_source` | no | Provenance label (e.g. `my_scanner_file`). |
| `observed_at` | no | Timestamp string. |

There is deliberately **no `required` field**. Required/advisory
classification is policy-owned and is derived from the policy at
evaluation time; a bundle that carries `required` on a `source-v0`
source fails closed as malformed input. A signal must not be able to
promote itself.

### Identity-completeness invariant

The `digest` must cover an identity object that **contains the `status`
and every decision-relevant observation** — everything your status was
derived from. Then two sources with equal digests cannot justify
different decisions, and a replayed record's inputs pin exactly what
was seen. The built-in helper enforces the mechanical half:

```python
from aos_workflow_gate.source_contract import source_digest

identity = {"tool": "my-scanner", "findings": 3, "status": "warning"}
source = {
    "id": "my-scanner",
    "kind": "scanner_summary",
    "status": identity["status"],
    "digest": source_digest(identity),  # rejects identity without status
    "contract": "source-v0",
}
```

The built-in adapters (check runs, SARIF, Scorecard, commit statuses)
follow the same invariant — one digest recipe family, no semantic
drift between built-in and external sources. The `branch.rules` summary
source is the documented exception: its digest is the `rules_digest`
temporal-drift primitive over the protection surface, and its status is
constant by construction.

### Status independence

The source status is independent from the policy verdict: `evaluate`
maps statuses to `PASS`/`WARN`/`BLOCK` only through the explicit policy
(required vs advisory, and the policy's rule severities). Your adapter
must never pre-judge — emit what you observed and let the policy decide.

### Normative canonicalization

The canonical form of a JSON value is exactly: the UTF-8 bytes of
serializing it with **sorted keys**, separators `","` and `":"` (no
insignificant whitespace), and non-ASCII characters kept verbatim
(`ensure_ascii: false`); the digest is the lowercase-hex SHA-256 of
those bytes, prefixed `sha256:`. In Python:

```python
json.dumps(value, ensure_ascii=False, sort_keys=True,
           separators=(",", ":"), allow_nan=False).encode("utf-8")
```

Committed **golden digest vectors** in
[examples/digest-vectors.json](../examples/digest-vectors.json) are
replayed by the test suite on every CI run; an implementation in any
language that reproduces every vector canonicalizes compatibly.
allow_nan=False excludes non-finite numbers from the canonical JSON domain.
Identity objects accept strings, integers, booleans, null, and containers
of those; floats are rejected at every nesting depth because their textual
form is implementation-sensitive. Encode exact numeric values as strings.

## Tamper detection and offline replay

Imported sources participate in the same evidence chain as collected
ones: the bundle is anchored by the record's `input_bundle_digest`, the
record self-verifies via `record_digest`, and `verify --input record
--bundle bundle` replays offline. When your source carries its
`identity`, the gate recomputes and verifies the digest and the
status-identity consistency itself; without it, the `digest` is an
opaque commitment that only holders of the identity object can check.
The built-in adapters attach their identity objects, so collected
bundles are self-verifying end to end.

## Migration from draft-0

`draft-0` bundle sources remain accepted indefinitely; a legacy
`required` field on them is type-checked and then **ignored** — the
record's required flags come from the policy either way. Committed
historical records are never rewritten. New integrations should emit
`source-v0` (set `contract: "source-v0"` explicitly for clarity).

## Boundary

Importing a source asserts nothing about its truthfulness: the gate
does not verify that your adapter honestly observed what it claims
(`signal_source` records provenance, not authenticity). No scanner
replacement, compliance, or security-audit claim is made.
