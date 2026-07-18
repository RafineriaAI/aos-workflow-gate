## Change

Describe the behavior or documentation changed and why it is needed.

## Verification

List the exact commands run and their results.

## Compatibility

- [ ] Existing decision records still replay, or the compatibility impact is documented.
- [ ] Verdict semantics, exit behavior, and advisory defaults are unchanged or explicitly reviewed.
- [ ] New behavior is covered by deterministic tests.

## Public Surface

- [ ] User-facing behavior and examples are documented.
- [ ] Claim boundaries remain accurate; no unsupported production, security, or compliance claim was added.
- [ ] `python tools/check_public_surface.py` passes.

## Release Impact

State `none`, `patch`, `minor`, or `major`, with a short reason.
