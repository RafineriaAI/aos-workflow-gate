# AOS Check mass-market value study

Status: `NO_GO_MASS_MARKET`.
Technical distribution: `TECHNICAL_DISTRIBUTION_READY`.
Free preview: `FREE_PREVIEW_TESTABLE`.

## Claim boundary

This study may measure repository-surface coverage, deterministic first-run behavior, diagnostic contrast with native commands, runtime, evidence hygiene, and activation requirements. It cannot establish human comprehension, business severity, recommendation acceptance, decision change, retention, willingness to pay, or defect-prevention efficacy without external users.

Public repository code was not executed. The repository arm reads public
metadata, root manifests, and tree shape at an exact commit. Controlled
execution uses generated fixtures only.

## Repository corpus

- Repositories: **500**.
- Static detection: **84.0%**; Wilson 95% CI **80.5% to 87.0%**.
- Discoverable behavioral surface: **68.8%**.
- Coverage-gap candidates: **12.0%**.
- Wrapper-only candidates: **68.8%**.
- Incomplete observations: **1.4%**.

| Search language | Repos | Detection | Behavioral surface | Gap candidate | Incomplete |
| --- | ---: | ---: | ---: | ---: | ---: |
| Python | 84 | 84.5% | 57.1% | 27.4% | 0.0% |
| TypeScript | 84 | 92.9% | 64.3% | 22.6% | 0.0% |
| JavaScript | 83 | 74.7% | 43.4% | 20.5% | 1.2% |
| Go | 83 | 91.6% | 91.6% | 0.0% | 2.4% |
| Rust | 83 | 90.4% | 87.9% | 1.2% | 0.0% |
| Java | 83 | 69.9% | 68.7% | 0.0% | 4.8% |

## Controlled first run

- Cases: **9**/**9**.
- Expected verdict accuracy: **100.0%**.
- Named Next on non-PASS: **100.0%**.
- Evidence hygiene: **100.0%**.
- Median result time: **1727 ms**; p95 **5241 ms**.
- Contrast beyond native nonzero exit: **44.4%**.
- Actionable coverage-gap proxy: **22.2%**.

The contrast metric is not a defect-detection lift. In v0, AOS mostly
orchestrates existing checks and adds a warning when behavioral evidence
is absent. Business importance is not established by this proxy.

## Historical review pain proxy

- Repositories: **120**; merged PRs: **446**.
- PRs with eligible human review: **175**.
- Semantically valid actionable PRs: **8/175 (4.6%)**.
- Medium/high-severity PRs: **6/175 (3.4%)**.
- Current AOS alignment: **0/9 valid signals (0.0%)**.

The final proxy excludes bots using GitHub actor types and uses token-boundary
matching. A single, non-independent evaluator then reviewed all 15 candidates.
It demonstrates that review pain exists, but does not demonstrate that the
current product detects it. Preliminary proxy outputs are retained only with
explicit correction manifests and are not valid product metrics.

## Noise audit

All **60** repository-corpus candidates behind the root-level missing-test
warning were re-read at the same commit using recursive Git tree paths.

- Definite conventional test surfaces: **12/60 (20.0%)**.
- Additional probable validation scripts: **3/60 (5.0%)**.
- Conservative false-warning rate: **20.0%**.
- Broader contradictory validation surface: **25.0%**.

This exceeds the preregistered 10% contradiction ceiling and blocks a
low-noise mass-market claim. The product must discover nested and monorepo
test surfaces or narrow the message to the exact observed fact: no runnable
test command was detected at this project root.

## Decision

The current implementation is suitable for technical testing as a free,
advisory preview. It is not ready for broad positioning as a code-quality
product: **68.8%** of repositories expose only wrapper-style value, the
audited warning has at least **20.0%** conservative noise, and alignment with
the adjudicated historical pain sample is **0.0%**.

Re-evaluation requires, in order:

1. nested/monorepo-aware runnable-test discovery and precise scope wording;
2. one deterministic, change-aware detector that identifies a code-risk gap
   beyond merely running existing project commands;
3. repetition of the corpus, noise, and historical-alignment measurements;
4. only after those pass, a free external alpha measuring comprehension,
   acceptance, decision change, retention, and willingness to pay.

## Comparator boundary

| Product | No Git path | Runs behavioral checks | Detects absent test surface | Finds new code issues | Replayable local decision |
| --- | --- | --- | --- | --- | --- |
| AOS Check v0 | yes | existing project checks | yes | no | yes |
| Native pytest/npm scripts | yes | yes | no aggregate warning | only their own checks | no |
| pre-commit | no; Git hook/config centered | configured hooks | no | hook-dependent | no |
| GitHub Actions | no; repository workflow | configured jobs | no | job-dependent | artifacts/checks |
| MegaLinter | local Docker/Node path | primarily linting | no | linter findings | reports, not AOS replay |
| Copilot code review | PR/account path | may use agentic tools | no deterministic contract | yes, probabilistic | no AOS-style record |
| SonarQube Cloud | Git/PR/service path | analysis, coverage input | coverage-dependent | yes | service history |

The matrix compares documented activation and output categories, not
precision or efficacy. No cross-product defect benchmark was run.

## External outcomes still required

- `alert_acceptance_rate`: unmeasured; threshold `0.5`.
- `business_relevant_incremental_rate`: unmeasured; threshold `0.2`.
- `comprehension_within_30_seconds_rate`: unmeasured; threshold `0.8`.
- `critical_false_positive_rate_max`: unmeasured; threshold `0.05`.
- `decision_change_rate`: unmeasured; threshold `0.1`.
- `first_result_completion_rate`: unmeasured; threshold `0.8`.
- `median_time_to_first_result_seconds_max`: unmeasured; threshold `300`.
- `minimum_external_participants`: unmeasured; threshold `30`.
- `minimum_novice_or_vibe_participants`: unmeasured; threshold `15`.
- `minimum_retention_days`: unmeasured; threshold `30`.
- `retention_rate`: unmeasured; threshold `0.4`.
- `willingness_to_pay_rate`: unmeasured; threshold `0.1`.

Even if the static blockers above are removed, these external outcomes remain
required. Until then, the only justified distribution is a free advisory
preview. A paid or broad correctness claim remains `NO_GO`.

## Sources

- [pytest invocation](https://docs.pytest.org/en/stable/how-to/usage.html)
- [pre-commit configuration and Git hooks](https://pre-commit.com/)
- [GitHub Actions workflows](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows)
- [MegaLinter local runner](https://megalinter.io/latest/mega-linter-runner/)
- [GitHub Copilot code review](https://docs.github.com/en/copilot/concepts/agents/code-review)
- [SonarQube Cloud pull request analysis](https://docs.sonarsource.com/sonarqube-cloud/improving/pull-request-analysis)
- [Stack Overflow 2025 AI survey](https://survey.stackoverflow.co/2025/ai)
- [DORA 2025 AI-assisted development](https://dora.dev/research/2025/dora-report/)

## Integrity

- Manifest digest: `sha256:31b79e21b06ff18915f3f3359bdd1a0a0474b1393009dde9d8128547415d8f09`.
- Corpus digest: `sha256:b860ef3e8f345a59295ecebfdd17f1fdfd3df47b257781b56765558425e01436`.
- Sample digest: `sha256:26d65f1a7ebe07e0f1d1dae3911201fe15bdb9652218a45a5ee4eddd5653ea99`.
