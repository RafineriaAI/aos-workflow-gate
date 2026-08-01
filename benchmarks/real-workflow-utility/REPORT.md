# Real-Workflow Utility Benchmark

## Result

- Mechanism: **PASS**
- Workflow utility signal: **NO_CLEAR_WORKFLOW_UTILITY**
- Sample: 10 cases / 5 matched pairs; 5 Polish-affiliated and 5 global.

This is a read-only workflow benchmark, not a user study. A contract-level contrast is not treated as proof that a maintainer would act.

## Measured

- First-run completion: 10/10
- Exact-SHA binding: 10/10
- Evidence integrity: 10/10
- Semantic replay: 10/10
- Complete collection at first observation: 7/10
- Workflow visibility available: 10/10
- Structurally complete non-PASS messages: 7/7
- Code/project-change findings among non-PASS: 0/7
- Workflow/repository-control findings among non-PASS: 7/7
- Naive non-success alerts avoided: 3/8
- AOS contract-level contrast: 4/10
- Contract contrasts without a same-snapshot visible non-success: 1/4
- Frozen human-outcome coverage: 2/5
- Historical action alignment: 0/2
- Material incremental alignment where outcome was available: 0/2
- Material incremental signal coverage: 0/10

## Cohorts

| Metric | Polish-affiliated | Global |
| --- | --- | --- |
| Cases | 5 | 5 |
| Verdicts | PASS 2 / WARN 2 / BLOCK 1 | PASS 1 / WARN 2 / BLOCK 2 |
| Contract contrast | 2/5 | 2/5 |
| Naive alerts avoided | 2/3 | 1/5 |
| Blinded human outcomes | 0/2 | 2/3 |

The cohorts are descriptive only. Five cases per cohort and zero eligible human outcomes in the Polish-affiliated cohort do not support a comparative utility claim.

## Cases

| Cohort | Repository / PR | AOS | GitHub baseline | Naive alert | Incremental by contract | Human alignment |
| --- | --- | --- | --- | --- | --- | --- |
| polish | [allegro/hermes#2052](https://github.com/allegro/hermes/pull/2052) | PASS | clear | yes | no | unavailable |
| global | [apache/kafka#23015](https://github.com/apache/kafka/pull/23015) | BLOCK | waiting | yes | no | unavailable |
| polish | [softwaremill/tapir#5442](https://github.com/softwaremill/tapir/pull/5442) | WARN | no_required_checks | yes | yes | unavailable |
| global | [scala/scala3#25393](https://github.com/scala/scala3/pull/25393) | PASS | clear | yes | no | unavailable |
| polish | [saleor/saleor#19587](https://github.com/saleor/saleor/pull/19587) | WARN | no_required_checks | no | yes | unavailable |
| global | [django/django#21681](https://github.com/django/django/pull/21681) | WARN | no_required_checks | yes | yes | none |
| polish | [VirtusLab/scala-cli#4403](https://github.com/VirtusLab/scala-cli/pull/4403) | PASS | clear | yes | no | insufficient |
| global | [sbt/sbt#9515](https://github.com/sbt/sbt/pull/9515) | WARN | no_required_checks | yes | yes | none |
| polish | [callstack/react-native-paper#5038](https://github.com/callstack/react-native-paper/pull/5038) | BLOCK | waiting | no | no | insufficient |
| global | [mui/material-ui#48888](https://github.com/mui/material-ui/pull/48888) | BLOCK | waiting | yes | no | insufficient |

## Practical reading

AOS completed quickly and produced intact, exact-SHA evidence. It also avoided three alerts that a naive all-non-success rule would emit.

The measured value is currently maintainer-facing: every non-PASS finding concerned repository or workflow controls. All four AOS/GitHub contrasts were `no_required_sources`; only one occurred without a same-snapshot visible non-success signal. The three BLOCK results explained states where GitHub already waited.

The two blinded, material human outcomes concerned code diagnostics and change blast radius. Neither aligned with the AOS finding. This sample therefore does not demonstrate a daily code-review assistant or a maintainer decision change.

Product implication: keep zero-config `check-pr` as a low-noise workflow control diagnostic. A broader developer product still needs code/diff-aware policies that produce concrete author actions and show material alignment with independent review outcomes.

## Interpretation

The benchmark can verify collection, exact-SHA evidence, low-noise treatment of expected states, and whether AOS explains a gap differently from GitHub. It cannot establish daily usefulness, action acceptance, decision change, retention, time saved, incident reduction, or willingness to pay.

Five cases violated the planned Stage A-before-AOS ordering and are excluded from blinded historical-action alignment. Silence, merge, and bot-only comments are not counted as acceptance or noise.
