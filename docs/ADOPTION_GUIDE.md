# Adoption Guide

This guide is for developers who understand pull requests and CI but do not
need to know AOS internals, formal methods, or supply-chain standards.

## One-sentence model

Existing tools produce signals. `aos-workflow-gate` turns those signals and
repository requirements into one explainable, replayable merge-control
decision.

## First value

Inspect any public pull request without a token or repository change:

```bash
python -m pip install "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.36.0"
aos-workflow-gate check-pr https://github.com/OWNER/REPO/pull/NUMBER
```

The result answers three questions:

1. What did AOS observe for this exact commit?
2. Which required control is satisfied, missing, pending, failed, or
   unverifiable?
3. What is the single next action?

For continuous use, copy the zero-config advisory workflow from
[README.md](../README.md). It needs no checkout, policy file, bundle, account,
telemetry, or code upload.

## Competency unblock

Only four concepts are needed:

- **Signal:** an observation such as a check run, commit status, or scanner
  summary.
- **Policy:** explicit rules that define required and advisory evidence.
- **Verdict:** `PASS`, `WARN`, or `BLOCK` for that policy.
- **Evidence record:** canonical JSON that binds subject, inputs, policy,
  verifier, reason, and digest for replay.

`UNSIGNED_NOT_OFFICIAL` means the record is content-addressed and
replay-checkable but not signed by RafineriaAI. A verdict does not certify
security, correctness, or compliance.

## Adoption ladder

1. Run `check-pr` locally on representative PRs.
2. Add the Action in advisory mode with automatic requirement discovery.
3. Compare named gaps and next actions with the repository's intended rules.
4. Keep advisory until repeated runs show stable requirements and acceptable
   noise.
5. Add a small explicit policy only where GitHub requirements do not model a
   real team rule.
6. Enable enforcement only after owners agree on override and rollback.

Do not begin with a broad policy catalog. One recurring, costly evidence gap is
a stronger adoption basis than many theoretical checks.

## Promotion criteria

Before enforcement, verify:

- exact-SHA collection is complete;
- required controls have stable app-bound identity;
- no permission or API failure is being mistaken for absence;
- each non-PASS result names one practical next action;
- owners can explain and replay the record;
- false positives are measured in that repository;
- rollback is a one-line workflow change.

## Barriers and design responses

| Barrier | Design response |
| --- | --- |
| Category sounds abstract. | Lead with “GitHub permits merge, AOS names the missing control” and show the exact PR. |
| A new check may create alert fatigue. | Advisory default, one dominant gap, bounded output, explicit policy promotion. |
| Zero configuration may infer the wrong intent. | Autodiscovery models only active GitHub requirements; explicit inputs fully replace it. |
| API or permission failures may look like success. | Preflight and collection fail closed with stable diagnostics. |
| Teams distrust opaque AI verdicts. | No LLM in the verdict path; canonical evidence, reason code, policy digest, verify, and replay. |
| Formal or security language obscures daily value. | Main output says what was checked, what is missing, effect, and next action; technical evidence is secondary. |
| A `BLOCK` could stop delivery unexpectedly. | Verdict and exit code are separate; advisory is default and enforcement is explicit. |

## Documentation path

- First run: [README](../README.md).
- Interpret output: [User FAQ](USER_FAQ.md).
- Diagnose access: [Preflight](PREFLIGHT.md).
- Configure CI: [CI Integrations](CI_INTEGRATIONS.md).
- Define policy: [Policy Packs](POLICY_PACKS.md).
- Verify trust and data boundaries: [Trust](TRUST.md),
  [Security Readiness](SECURITY_READINESS.md), and [Scope](SCOPE.md).
- Contribute: [Contributing](../CONTRIBUTING.md) and
  [Development Guide](DEVELOPMENT.md).

## Research inputs

The documentation structure follows task-first GitHub README guidance and
Diataxis. Interaction design follows progressive disclosure and
recognition-over-recall: the main result is concise, while digests and replay
remain available as technical evidence. GitHub Actions integrations follow
least privilege and pinned third-party actions.

Reference sources:

- https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes
- https://diataxis.fr/
- https://www.nngroup.com/articles/ten-usability-heuristics/
- https://docs.github.com/en/actions/reference/security/secure-use
- https://github.com/ossf/scorecard
