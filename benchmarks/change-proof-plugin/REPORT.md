# AOS as a plug-in to existing tests

## Decision

- Direction: **CONTINUE_NARROW_PLUGIN_EXPERIMENT**
- Default enablement: **DO_NOT_ENABLE_BY_DEFAULT**
- ROI: **UNPROVEN_REQUIRES_EXTERNAL_USE**

The strongest current product question is:

> The tests pass, but would they still pass without the implementation change?

AOS should answer this as a plug-in after an existing targeted test command. It should not replace the test runner, coverage service, scanner, or reviewer.

## What the experiment found

- Real merged pull requests that changed code and tests, where the tests distinguished the implementation: 5/5.
- Controlled run where the verifier omitted every changed test file, and AOS warned: 1/1.
- Behavior-preserving or performance changes where raw AOS warned even though adding a functional test was not the right action: 2/2.
- Those noisy recommendations avoided by the calibrated scope: 2/2.
- Evidence integrity and semantic replay: 8/8.

The useful calibration is therefore simple: run Change Proof when a pull request changes implementation and tests, or when an operator explicitly declares that the verifier should observe a behavior change. Skip ordinary functional Change Proof for behavior-preserving and performance-only work.

## Cost

AOS executed one HEAD run and two challenge runs. Median verifier work was 3.157x one HEAD run (5.611 seconds in this small, fast sample); median CLI wall time was 7.008 seconds.

This is acceptable for a targeted fast test command. It is not acceptable as an unconditional replay of a large test suite.

## Where it fits

| Existing tool | What it proves | What Change Proof adds |
| --- | --- | --- |
| GitHub required checks | A registered result reached an accepted status for the commit | Whether the supplied verifier notices removal of the actual PR implementation |
| Codecov patch coverage | Changed lines executed | Whether test outcomes change; execution alone does not prove a meaningful assertion |
| Stryker or PIT | Tests kill many small synthetic mutants | One coarse, language-neutral counterfactual aligned with the submitted patch |
| SonarQube PR analysis | New static-analysis issues and quality-gate metrics | Dynamic sensitivity of the operator's own verifier |

This is differentiated, not category-exclusive. Mutation testing is the closest established alternative and is stronger for fine-grained test quality. AOS may be easier to add across languages because it needs a Git diff and an existing command, but that advantage is not yet measured.

## ROI gate

Do not enable by default or define a paid offer until external use meets all of these conditions:

1. At least 50 eligible pull requests across at least five independent repositories.
2. At least 50% of warnings lead to an accepted test or verifier improvement.
3. No more than 10% of warnings are judged irrelevant or wrong.
4. No more than 10% of runs are inconclusive after one retry.
5. Median added wall time stays below two minutes for the selected verifier.
6. Setup takes at most ten minutes in at least 80% of repositories.
7. At least 20% of accepted warnings change merge readiness or catch a weak test before review.
8. At least half of trial repositories retain the plug-in after four weeks.

The economic check is: expected avoided review and regression cost must exceed extra runner time plus warning-review time. The current study has no external accepted warning, decision change, retention, or willingness-to-pay observation, so ROI remains unproven.

## Cases

| Cohort | Pull request | Raw AOS | Calibrated action | Interpretation |
| --- | --- | --- | --- | --- |
| observed code and tests | [pallets/click#3678](https://github.com/pallets/click/pull/3678) | PASS | run | bounded reassurance |
| observed code and tests | [pytest-dev/pluggy#617](https://github.com/pytest-dev/pluggy/pull/617) | PASS | run | bounded reassurance |
| observed code and tests | [hynek/structlog#805](https://github.com/hynek/structlog/pull/805) | PASS | run | bounded reassurance |
| observed code and tests | [python-attrs/attrs#1593](https://github.com/python-attrs/attrs/pull/1593) | PASS | run | bounded reassurance |
| observed code and tests | [more-itertools/more-itertools#1223](https://github.com/more-itertools/more-itertools/pull/1223) | PASS | run | bounded reassurance |
| observed behavior preserving control | [hynek/structlog#821](https://github.com/hynek/structlog/pull/821) | WARN | skip | noisy if run by default |
| observed behavior preserving control | [more-itertools/more-itertools#1161](https://github.com/more-itertools/more-itertools/pull/1161) | WARN | skip | noisy if run by default |
| controlled under scoped verifier | [pallets/click#3678](https://github.com/pallets/click/pull/3678) | WARN | run | mechanism only actionable |

## Limits

This exploratory benchmark establishes bounded mechanism behavior and a low-noise trigger hypothesis. It does not establish alert precision, avoided defects, decision impact, retention, willingness to pay, or superiority over coverage or mutation testing.

The sample is exploratory, selected for reproducibility, Python-only, and contains one controlled counterfactual. It supports the next experiment, not a product-value or superiority claim.
