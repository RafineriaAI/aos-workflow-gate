# Hybrid Value Gate

**Publication status: `NO_GO`**

This is a product-publication decision, not a merge-readiness verdict. Signal validity, internal product-test readiness, external usability, and field utility are separate claims. Internal tests and public repository history are never user evidence.

## Track status

- Signal validity: `SIGNAL_INCONCLUSIVE`.
- Internal product test: `PRODUCT_TEST_READY`.
- External study: `EXTERNAL_STUDY_NOT_READY`.
- External usability: `EXTERNAL_VALIDATION_PENDING`.
- Field utility: `FIELD_VALIDATION_PENDING`.

## Measured signal sample

- Cases: **100** across **10** repositories.
- Complete metadata streams: **100** (100%).
- Self-validating workflow signal: **7** cases across **5** repositories; **2** bot-authored.
- Keyword-matched CI/test inline review comments: **22** across **12** PRs.
- Exact-baseline actionable findings: **0**; independently labeled signal cases: **0**.

## Product-test readiness

- Internal checks: **6**/**6** met.
- External participants currently available: **no**.
- External teams currently available: **no**.
- Qualified external users observed: **0**.
- Internal checks can establish only PRODUCT_TEST_READY; they cannot establish product usefulness, adoption, retention, or willingness to pay.

## Acceptance criteria

| Track | Criterion | Observed | Required | Result |
| --- | --- | --- | --- | --- |
| `signal_validity` | `sample_scale` | `100` | `>= 100` | **met** |
| `signal_validity` | `repository_diversity` | `10` | `>= 10` | **met** |
| `signal_validity` | `collection_completeness` | `1.000` | `>= 0.950` | **met** |
| `signal_validity` | `recurring_signal` | `cases=7, repositories=5` | `>= each cases=3, repositories=3` | **met** |
| `signal_validity` | `exact_incremental_findings` | `cases=0, repositories=0` | `>= each cases=3, repositories=3` | **not met** |
| `signal_validity` | `precision_sample` | `0` | `>= 20` | **not met** |
| `signal_validity` | `observed_precision` | `unavailable` | `>= 0.950` | **not met** |
| `product_test_readiness` | `product_adversarial_ux` | `met` | `== met` | **met** |
| `product_test_readiness` | `product_clean_room_install` | `met` | `== met` | **met** |
| `product_test_readiness` | `product_deterministic_diagnosis` | `met` | `== met` | **met** |
| `product_test_readiness` | `product_external_protocol_frozen` | `met` | `== met` | **met** |
| `product_test_readiness` | `product_first_run_path` | `met` | `== met` | **met** |
| `product_test_readiness` | `product_verdict_task_corpus` | `met` | `== met` | **met** |
| `external_usability` | `controlled_comparative_study` | `not_run` | `== verified` | **not met** |
| `external_usability` | `qualified_external_users` | `0` | `>= 8` | **not met** |
| `external_usability` | `next_action_clarity` | `unavailable` | `>= 1.000` | **not met** |
| `external_usability` | `retention` | `unavailable` | `>= 1.000` | **not met** |
| `external_usability` | `comprehension_time` | `unavailable` | `<= 30` | **not met** |

## Decision rule

- `SIGNAL_SUPPORTED + PRODUCT_TEST_READY` permits only a controlled external study; it does not permit publication.
- `GO` additionally requires `EXTERNAL_USABILITY_SUPPORTED`.
- Commercialization remains unvalidated until a separate field study establishes practical utility and retention.
- `NO_GO` blocks publication, marketing, production recommendations, and paid pilot intake.

Current publication blockers: `exact_incremental_findings`, `precision_sample`, `observed_precision`, `controlled_comparative_study`, `qualified_external_users`, `next_action_clarity`, `retention`, `comprehension_time`.
