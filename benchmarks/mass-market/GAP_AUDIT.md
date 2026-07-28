# Missing-test-surface path audit

Status: `HIGH_FALSE_POSITIVE_RISK`.

- Candidates: **60**.
- Complete recursive trees: **100.0%**.
- Contradicted by test paths/config: **18** (30.0%).
- No test path/config found: **42** (70.0%).
- Inconclusive: **0**.

A path proves test material exists, not that it is runnable or relevant
to the selected project root. No path does not prove absence of behavioral
validation. This audit measures false-warning risk, not business value.

Manifest: `sha256:7570c5f560e83daa9f864a06c3ce46f9ac19eee439700c0d5291413cb4ef585d`.
Corpus: `sha256:b860ef3e8f345a59295ecebfdd17f1fdfd3df47b257781b56765558425e01436`.
