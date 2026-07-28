# Historical review pain proxy

Status: `REAL_PAIN_FOUND_AOS_GAP`.

## Boundary

Final merged history cannot reconstruct what checks failed before merge, prove that AOS would have changed a decision, or establish causality. Keyword classification may contain false positives and false negatives.

This is a deterministic keyword-and-state proxy over public history. It
does not show how a maintainer reacts to AOS and cannot establish causality,
decision change, acceptance, retention, willingness to pay, or precision.
Raw review text is not stored; public URLs and body digests preserve audit
references.

## Sample

- Repositories selected: **120**; collected: **120**.
- Merged PRs: **450**.
- PRs with eligible human review: **209**.
- Human review artifacts: **602**.
- Truncated PR observations: **8**.

## Results

- PRs with actionable review pain: **34** (16.3% of reviewed PRs).
- Actionable signal instances: **47**.
- Current AOS alignment among actionable instances: **0.0%**.
- Business-relevant incremental alignment: **0.0%**.
- Maintainer-action proxy instances: **44**.

| Category | Interventions |
| --- | ---: |
| api_contract_docs | 11 |
| reliability_edge_case | 19 |
| security_permissions | 11 |
| tests | 36 |

## Interpretation

`REAL_PAIN_FOUND_AOS_GAP` means reviewers demonstrably intervene on daily
changes, but the current project-level AOS signal rarely aligns with those
interventions. This supports product discovery, not a product-value claim.

## Integrity

- Manifest digest: `sha256:444dbc5d0f0d9c330a3097cd0bbff7e54fd0e74fd7adb203e6fef96273bba033`.
- Source corpus digest: `sha256:b860ef3e8f345a59295ecebfdd17f1fdfd3df47b257781b56765558425e01436`.
