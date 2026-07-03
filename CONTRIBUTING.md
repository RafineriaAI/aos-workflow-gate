# Contributing

This repository is intentionally narrow. Contributions should improve the workflow gate without expanding claims beyond implemented behavior.

## Preferred changes

- Clarify scope, use cases, architecture, or adoption barriers.
- Add deterministic tests once implementation starts.
- Add minimal adapters with explicit input and output contracts.
- Improve evidence integrity without adding unsupported compliance claims.

## Avoid

- Production-ready, compliance, signing, SLSA, or security-audit claims before the relevant implementation and evidence exist.
- Broad workflow orchestration features that belong outside the gate.
- Hidden policy behavior.
- Dependencies that are not needed for the current phase.

## Review checklist

Before a change is merged, check:

- Does the README still make the current status clear?
- Does the change preserve `PASS/WARN/BLOCK` semantics?
- Does the change keep advisory mode separate from blocking mode?
- Does the change avoid unsupported trust, security, or compliance claims?
- Does a new behavior have a replayable evidence path?
