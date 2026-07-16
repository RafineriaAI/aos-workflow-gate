# Hybrid Value Gate

**Product-claim status: `NO_GO`**

This is a product-claim decision, not a merge-readiness verdict. A free advisory release is a validation channel, not evidence of usefulness or market demand. Exact-SHA contrast can establish only a semantic difference from GitHub. Internal utility tasks establish only testability of the diagnosis, not practical usefulness. Signal validity, product testability, external usability, and field utility are separate claims. Internal tests and public repository history are never user evidence.

## Track status

- Mechanism evidence: `MECHANISM_CONFIRMED`.
- Signal validity: `SIGNAL_INCONCLUSIVE`.
- Internal product test: `PRODUCT_TEST_READY`.
- Practical-utility testability: `UTILITY_TEST_READY`.
- External-test readiness: `READY_FOR_EXTERNAL_VALIDATION`.
- Participant access: `RECRUITMENT_PENDING`.
- Validation distribution: `FREE_SELF_SERVE_VALIDATION`.
- External usability: `EXTERNAL_VALIDATION_PENDING`.
- Field utility: `FIELD_VALIDATION_PENDING`.

## Measured signal sample

- Cases: **100** across **10** repositories.
- Complete metadata streams: **100** (100%).
- Self-validating workflow signal: **7** cases across **5** repositories; **2** bot-authored.
- Keyword-matched CI/test inline review comments: **22** across **12** PRs.
- Exact-baseline actionable findings: **0**; independently labeled signal cases: **0**.

## Exact-SHA semantic contrast

- GitHub `clean` plus AOS `WARN/non_independent_evidence`: **3** cases across **3** repositories.
- Full canonical bundle/policy/record replay: **2** cases.
- A required GitHub check was non-independent: **1** case(s), **1** source(s).
- Independently adjudicated contrast outcomes: **0**.
- Interpretation: semantic difference is demonstrated; usefulness and precision remain unproven until outcomes are independently labeled.

## Product-test readiness

- Internal checks: **6**/**6** met.
- External participants currently available: **no**.
- External teams currently available: **no**.
- Qualified external users observed: **0**.
- Free self-serve validation available: **yes** (`advisory`, telemetry: `none`).
- Internal checks can establish only PRODUCT_TEST_READY; they cannot establish product usefulness, adoption, retention, or willingness to pay.

## Practical-utility testability

- Frozen internal tasks: **8**; positive controls: **2**; negative controls: **6**.
- Internal checks: **7**/**7** met.
- These tasks verify deterministic diagnosis and one actionable Next. They do not measure whether an external developer understands, trusts, uses, retains, or pays for the product.

## Acceptance criteria

| Track | Criterion | Observed | Required | Result |
| --- | --- | --- | --- | --- |
| `mechanism_evidence` | `exact_semantic_contrast` | `cases=3, repositories=3` | `>= each cases=3, repositories=3` | **met** |
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
| `practical_utility_testability` | `utility_advisory_effect` | `met` | `== met` | **met** |
| `practical_utility_testability` | `utility_claim_firewall` | `met` | `== met` | **met** |
| `practical_utility_testability` | `utility_contrast_task` | `met` | `== met` | **met** |
| `practical_utility_testability` | `utility_deterministic_replay` | `met` | `== met` | **met** |
| `practical_utility_testability` | `utility_low_noise_controls` | `met` | `== met` | **met** |
| `practical_utility_testability` | `utility_single_next_action` | `met` | `== met` | **met** |
| `practical_utility_testability` | `utility_verdict_coverage` | `met` | `== met` | **met** |
| `external_usability` | `controlled_comparative_study` | `not_run` | `== verified` | **not met** |
| `external_usability` | `qualified_external_users` | `0` | `>= 8` | **not met** |
| `external_usability` | `next_action_clarity` | `unavailable` | `>= 1.000` | **not met** |
| `external_usability` | `retention` | `unavailable` | `>= 1.000` | **not met** |
| `external_usability` | `comprehension_time` | `unavailable` | `<= 30` | **not met** |

## Decision rule

- `MECHANISM_CONFIRMED` proves only that AOS can produce decision-relevant information absent from the observed GitHub baseline.
- `READY_FOR_EXTERNAL_VALIDATION` requires confirmed mechanism, internal product readiness, and the frozen utility-task corpus. `SIGNAL_INCONCLUSIVE` may be studied; `SIGNAL_NOT_SUPPORTED` blocks it.
- `READY_FOR_EXTERNAL_VALIDATION` permits recruitment and a controlled advisory study. It is not `PRODUCT_USEFUL`, paid-pilot readiness, or a production recommendation.
- `FREE_SELF_SERVE_VALIDATION` permits a public, no-cost advisory technical preview with no telemetry. Availability, installs, and downloads are funnel observations, not usefulness evidence.
- `GO` additionally requires `SIGNAL_SUPPORTED` and independently supported external usability.
- Commercialization remains unvalidated until a separate field study establishes practical utility and retention.
- `NO_GO` blocks efficacy or value claims, production recommendations, and paid pilot intake. It does not block the declared free advisory validation channel.

Current product-claim blockers: `exact_incremental_findings`, `precision_sample`, `observed_precision`, `controlled_comparative_study`, `qualified_external_users`, `next_action_clarity`, `retention`, `comprehension_time`.
