# Adversarial regression corpus

This corpus freezes cases that must remain stable as collection,
decision, and verification logic evolves. It complements the
real-history benchmark; it does not extend that benchmark's empirical
claim.

## Boundary

All cases here are deterministic regression fixtures. Decision cases
contain synthetic bundles and policies. Verification cases apply a
small, enumerated mutation to an existing committed record/bundle pair.
They are not production incidents, market evidence, vulnerability
claims, or proof that defects are absent.

Expected outcomes are read only by the test harness. They never enter
the product evaluator or verifier. The harness executes no arbitrary
commands and resolves every referenced file inside the repository.

## Surfaces

- [cases](cases/) cover policy decisions, including PASS, WARN, and
  BLOCK controls.
- [bindings](bindings/) cover record-to-bundle subject correlation,
  observation scope, verifier manifests, and compatibility disclosure.
- [MATRIX.md](MATRIX.md) is generated from corpus metadata and states
  the complete coverage taxonomy.

The GitHub-baseline contrast intentionally excludes these synthetic
fixtures. See [the committed contrast](../contrast/CONTRAST.md) for
evidence-backed baseline rows.

## Reproduce

    python -m pytest \
      tests/test_adversarial_corpus.py \
      tests/test_adversarial_bindings.py

    python tools/adversarial_matrix.py

CI regenerates the matrix in memory and requires byte-identical output.
Every decision case must reproduce its exact ordered reason-code list;
every binding case must reproduce its exit code and disclosure class.
