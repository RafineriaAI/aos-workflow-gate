# Should AOS continue?

## Decision

- Product direction: **NARROW_OR_PIVOT**
- Community release: **OPEN_AS_EXPERIMENTAL_PREVIEW**
- Mechanism: **PASS**
- Holdout: 10 real pull requests; 5 Polish-affiliated and 5 global.

## In plain language

AOS ran reliably and explained one required GitHub check that did not run. It did not identify any of the material code, data, runtime or review problems independently found by people in this holdout.

That means the current GitHub gate may help maintainers understand repository controls, but this benchmark does not support positioning it as a general daily code-review assistant.

The repository can be shared as a free experiment if it says this clearly. Community use should be treated as problem discovery, not proof that the product is already needed.

## Wniosek po polsku

Mechanizm działa poprawnie, ale w tej próbie AOS nie wskazał żadnej nowej czynności odpowiadającej istotnym problemom znalezionym przez ludzi. Warto zachować wąską kontrolę workflow i udostępnić projekt bezpłatnie jako eksperyment. Nie ma jeszcze podstaw, by przedstawiać go jako ogólnego pomocnika do recenzji kodu.

## What was measured

- Exact commit and replay integrity: 10/10
- Human review outcome available: 10/10
- Non-PASS messages understandable without internal terms: 7/7
- New useful action not already visible in GitHub: 0/10
- Useful explanation of an existing GitHub state: 1/10
- Material human-review problems matched by AOS: 0/6
- Material human-review problems missed by AOS: 6/6
- Median time to result: 6.803 seconds

## Who may need it

- Maintainers who rely on GitHub required checks and need to know why one did not run.
- Teams that want a replayable record of the checks used for one exact commit.
- Open-source contributors willing to test whether other repository rules should be modeled.

## Who probably does not need it yet

- A developer looking for code review, bug finding or architecture advice.
- A small repository with no required GitHub checks.
- A team expecting proof that PASS means the code is safe.

## Holdout cases

| Cohort | Pull request | AOS | Human issue | Value class |
| --- | --- | --- | --- | --- |
| polish | [mirumee/ariadne#1334](https://github.com/mirumee/ariadne/pull/1334) | WARN | test quality and state handling | unrelated |
| global | [strawberry-graphql/strawberry#4554](https://github.com/strawberry-graphql/strawberry/pull/4554) | PASS | input validation behavior regression | unrelated |
| polish | [Sylius/Sylius#19134](https://github.com/Sylius/Sylius/pull/19134) | PASS | misleading user validation | unrelated |
| global | [shopware/shopware#18878](https://github.com/shopware/shopware/pull/18878) | PASS | runtime environment regression | unrelated |
| polish | [TheWidlarzGroup/react-native-video#5016](https://github.com/TheWidlarzGroup/react-native-video/pull/5016) | WARN | android build compatibility | unrelated |
| global | [react-native-webview/react-native-webview#3984](https://github.com/react-native-webview/react-native-webview/pull/3984) | WARN | incorrect test provenance and release confidence | duplicate |
| polish | [TouK/nussknacker#9416](https://github.com/TouK/nussknacker/pull/9416) | WARN | high availability split brain and duplicate work | unrelated |
| global | [apache/flink#28850](https://github.com/apache/flink/pull/28850) | WARN | localized documentation quality | unrelated |
| polish | [deepsense-ai/ragbits#977](https://github.com/deepsense-ai/ragbits/pull/977) | WARN | data model and maintenance cost | unrelated |
| global | [run-llama/llama_index#22517](https://github.com/run-llama/llama_index/pull/22517) | BLOCK | default query path runtime failure | useful explanation |

## Recommended next move

Keep the exact-commit workflow gate narrow. Before adding more platform features, test one diff-aware rule that can name a file, explain a real risk and propose an action that matches independent human review.

Open development to the community only as a free experimental preview. Ask contributors for falsifiable cases: a missed required control, a wrong warning, or a concrete review action AOS should have suggested.

## Limits

This is a read-only historical workflow study, not a live user trial. It can test exact-commit behavior, alignment with public human review, message clarity proxies and community-readiness mechanics. It cannot prove adoption, retention, willingness to pay, time saved, decision change in live use or defect prevention.

This historical holdout cannot measure actual adoption, retained use, accepted recommendations, live decision changes, time saved or willingness to pay.
