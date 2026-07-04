# Decision Record Predicate (v0)

`aos-workflow-gate export` wraps a verified decision record in an in-toto
Statement (v1) so existing supply-chain tooling can bind the gate decision
to the gated commit and sign it with operator-held keys.

Predicate type identifier:

```text
https://github.com/RafineriaAI/aos-workflow-gate/decision-record/v0
```

## Statement shape

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {
      "name": "git+https://github.com/<owner>/<repo>[@<ref>]",
      "digest": { "gitCommit": "<40-hex commit sha>" }
    }
  ],
  "predicateType": "https://github.com/RafineriaAI/aos-workflow-gate/decision-record/v0",
  "predicate": { "…full decision record…" }
}
```

The predicate is the complete, unmodified decision record
(`aos-workflow-gate-decision/v0`), including its `record_digest` self-digest
and `UNSIGNED_NOT_OFFICIAL` verification status. `export` refuses a record
that fails its self-digest check, so a tampered record cannot be exported.

## Signing with operator-held keys

The exported Statement is UNSIGNED and must not be called an attestation
until it is signed. Operators can sign it with keys they already control,
for example with cosign:

```bash
aos-workflow-gate export \
  --input examples/aos-kernel-gate-decision.json \
  --out gate-statement.json

cosign sign-blob --yes gate-statement.json \
  --output-signature gate-statement.sig \
  --output-certificate gate-statement.pem
```

A signature made this way is the operator's own claim over the decision
record. It is not an official RafineriaAI/AOS verdict; official signing,
publication, and verification controls remain future work.

## Boundary

This export makes no SLSA level, provenance, SBOM, or compliance claim. It
binds a gate decision to a commit in a standard envelope — nothing more.
