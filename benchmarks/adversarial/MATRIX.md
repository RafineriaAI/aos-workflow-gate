# Adversarial regression coverage

Generated deterministically from committed corpus metadata.
Decision fixtures and verification mutations are synthetic
regression controls. They are not production incidents, market
evidence, or GitHub-baseline contrast rows.

| Case | Surface | Classification | Mechanism | Expected |
| --- | --- | --- | --- | --- |
| `cross-sha-observation-fail-closed` | decision | `negative_control` | `observation_scope` | **BLOCK** |
| `duplicate-provenance-single-control` | decision | `neutral_control` | `requirement_provenance` | **PASS** |
| `foreign-subject-missing` | decision | `negative_control` | `subject_validation` | **BLOCK** |
| `freshness-unverified-required` | decision | `negative_control` | `agent_action_freshness` | **BLOCK** |
| `imposter-app-unverifiable` | decision | `negative_control` | `control_identity` | **BLOCK** |
| `incomplete-collection-clean` | decision | `negative_control` | `collection_completeness` | **WARN** |
| `legacy-status-app-bound-rejected` | decision | `negative_control` | `legacy_status_boundary` | **BLOCK** |
| `legacy-status-unbound-success` | decision | `positive_control` | `legacy_status_boundary` | **PASS** |
| `same-context-apps-both-satisfied` | decision | `positive_control` | `control_identity` | **PASS** |
| `same-context-apps-one-unverifiable` | decision | `negative_control` | `control_identity` | **BLOCK** |
| `self-promoting-source` | decision | `negative_control` | `policy_ownership` | **BLOCK** |
| `status-identity-lie` | decision | `negative_control` | `source_identity` | **BLOCK** |
| `tampered-identity` | decision | `negative_control` | `source_integrity` | **BLOCK** |
| `zero-required-all-green` | decision | `negative_control` | `empty_policy` | **WARN** |
| `cross-subject-rebound` | verification | `negative_control` | `record_subject_binding` | **REJECT** |
| `different-valid-manifest` | verification | `neutral_control` | `verifier_manifest_binding` | **ACCEPT_WITH_DISCLOSURE** |
| `digest-only-record` | verification | `neutral_control` | `backward_compatibility` | **ACCEPT_WITH_DISCLOSURE** |
| `exact-record-bundle` | verification | `positive_control` | `record_subject_binding` | **ACCEPT** |
| `exact-subject-context` | verification | `positive_control` | `context_snapshot_binding` | **ACCEPT** |
| `future-manifest-schema` | verification | `neutral_control` | `forward_compatibility` | **ACCEPT_WITH_DISCLOSURE** |
| `historical-pre-manifest` | verification | `neutral_control` | `backward_compatibility` | **ACCEPT_WITH_DISCLOSURE** |
| `incomplete-context-binding` | verification | `negative_control` | `context_snapshot_binding` | **REJECT** |
| `invalid-context-digest` | verification | `negative_control` | `context_snapshot_binding` | **REJECT** |
| `invalid-embedded-manifest` | verification | `negative_control` | `verifier_manifest_binding` | **REJECT** |
| `observation-scope-mismatch` | verification | `negative_control` | `observation_scope` | **REJECT** |
| `record-observation-scope-mismatch` | verification | `negative_control` | `observation_scope` | **REJECT** |

## Coverage summary

- Total cases: **26**
- Positive controls: **4**
- Negative controls: **17**
- Neutral controls: **5**
- Mechanisms: **16**

Mechanisms: `agent_action_freshness`, `backward_compatibility`, `collection_completeness`, `context_snapshot_binding`, `control_identity`, `empty_policy`, `forward_compatibility`, `legacy_status_boundary`, `observation_scope`, `policy_ownership`, `record_subject_binding`, `requirement_provenance`, `source_identity`, `source_integrity`, `subject_validation`, `verifier_manifest_binding`.

Expected outcomes are consumed only by the test harness. The
product evaluator and verifier receive only materialized
bundle, policy, record, and manifest inputs.
