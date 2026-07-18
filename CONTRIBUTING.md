# Contributing

`aos-workflow-gate` is a public advisory preview. Contributions must preserve
its deterministic decision model, replay path, read-only defaults, and explicit
claim boundaries.

## First setup

Prerequisites: Git and Python 3.11 or newer. CI validates Python 3.11 and 3.14.
The package has no runtime dependencies; the `dev` extra contains every tool
needed by the test suite, including wheel-build dependencies.

POSIX:

```bash
git clone https://github.com/RafineriaAI/aos-workflow-gate.git
cd aos-workflow-gate
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

PowerShell:

```powershell
git clone https://github.com/RafineriaAI/aos-workflow-gate.git
Set-Location aos-workflow-gate
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Confirm the clean checkout before editing:

```bash
python -m ruff check .
python -m mypy
python -m pytest
python tools/check_public_surface.py
```

Read [Development Guide](docs/DEVELOPMENT.md) for the module map, invariants,
test ownership, and documentation update rules.

## Change workflow

1. Create a focused branch from current `main`.
2. Add or update the closest deterministic test with the behavior change.
3. Keep contracts backward compatible unless the PR explicitly defines a
   migration and historical replay coverage.
4. Update the canonical user or maintainer document named in the development
   guide; do not duplicate the same instructions across documents.
5. Run all four checks above and record the commands in the pull request.
6. Open a pull request and complete the repository template.

Commit messages should describe the observable change, for example:
`fix: preserve app-bound control identity during collection`.

## Review requirements

CODEOWNERS routes review to the current maintainer. Changes to verdict
semantics, canonicalization, evidence digests, source contracts, permissions,
release controls, or public claims require explicit maintainer review.

A contribution is ready when:

- behavior is deterministic and covered by tests;
- existing committed records and benchmark cases still replay;
- malformed or incomplete mandatory evidence cannot become `PASS`;
- verdict and process exit behavior remain distinct;
- advisory remains the default;
- documentation and examples match the implemented surface;
- no unsupported production, compliance, security-audit, signing, SLSA, or
  efficacy claim was introduced.

## Scope discipline

Prefer narrowly scoped fixes, adapters with explicit contracts, low-noise
diagnostics, replay integrity, and self-serve usability. Avoid hidden policy
behavior, workflow orchestration, automatic remediation, unnecessary runtime
dependencies, or features outside the current scope lock.

Security reports do not belong in public issues. Follow
[SECURITY.md](SECURITY.md).
