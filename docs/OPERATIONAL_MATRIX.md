# Operational Compatibility Matrix

This matrix records deterministic regression coverage for the current
Preview release. It proves the listed mechanics under controlled fixtures;
it does not prove everyday usefulness, production reliability, low noise, or
compatibility with every external repository.

| Environment or edge case | Required behavior | Regression evidence |
| --- | --- | --- |
| Nested monorepo projects | Discover bounded nested Node.js and Python roots; execute checks in each project directory. | tests/test_project_check.py::test_nested_node_project_supplies_behavioral_test_without_root_warning; tests/test_project_check.py::test_nested_python_project_runs_in_its_own_directory |
| Many workflows | Preserve more than one page of check suites and disclose truncation. | tests/test_workflow_state.py::test_check_suites_pagination |
| Many check runs | Collect every page within the declared API budget without collapsing names. | tests/test_resilience.py::test_check_run_pagination_keeps_all_pages |
| Fork and draft PR | Preserve both context flags, show the operator notes, and never weaken a missing required control. | tests/test_check_pr.py::test_check_pr_reports_fork_and_draft_without_weakening_policy |
| Jenkins and legacy commit statuses | Normalize success, pending, failure, and error; allow only unbound requirements to be satisfied by legacy status identity. | tests/test_check_pr.py::test_status_sources_mapping_and_precedence; tests/test_semantic_correctness.py::test_legacy_status_resolves_provisional_check_run_gap |
| Matrix GitHub Actions jobs | Keep exact matrix job names as distinct control identities. | tests/test_requirements.py::test_matrix_jobs_remain_distinct_controls |
| Conditional or skipped jobs | Preserve the literal skipped result and separately record GitHub's merge-equivalent semantics. | tests/test_semantic_correctness.py::test_skipped_required_matches_github_in_zero_config |
| Approval-required workflow | Record action_required as visible evidence; classify it as missing only when an explicit requirement exists. | tests/test_workflow_state.py::test_expected_and_not_started_still_fails_closed |
| Exact commit binding | Reject or disclose observations from another head SHA. | tests/test_semantic_correctness.py::test_observation_is_bound_to_exact_head_sha |
| Rulesets plus classic Branch Protection | Union control identities and retain requirement provenance. | tests/test_semantic_correctness.py::test_discovery_unions_rulesets_and_classic |
| Partial API visibility | Continue only when evaluation remains bounded; otherwise fail closed or return an operational error. | tests/test_integrated_preflight.py::test_check_pr_continues_when_statuses_degrade; tests/test_resilience.py::test_api_call_budget_is_enforced |

## Platform Boundary

GitHub has native online collection. Jenkins, GitLab, CircleCI, and other
systems can use the platform-neutral evaluator with explicit source-v0
evidence, but their collection completeness remains the adapter or operator's
claim. A GitLab online collector is not implemented.

These cases are release regressions, not external field results. Maturity
cannot advance beyond Preview from this matrix alone.
