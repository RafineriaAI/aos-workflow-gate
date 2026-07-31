# Historical Noise Control: Expected Skipped Check

> This is a retained historical replay fixture, not a value claim. The record
> correctly reports what its explicit policy said in 2026: every non-success
> advisory result became `WARN`. The underlying job was skipped **by design**
> on pull requests, so the warning was operational noise.

## The 60-second version

- The exact PR head and GitHub check results are real and committed.
- The required CI check passed.
- `AOS Workflow Gate Self / no-checkout` was non-required and expected to skip.
- The historical explicit policy promoted that expected skip to `WARN`.
- No maintainer action or AOS-driven decision change was observed.
- Current zero-config defaults retain the skipped observation as evidence but
  do not raise a warning for it.

Outcome: `noise`. The case is useful because it separates a technically correct
observation from a useful decision.

## What the record proves

The committed [record](../../examples/green-but-incomplete-record.json),
[bundle](../../examples/green-but-incomplete-bundle.json), and
[policy](../../examples/green-but-incomplete-policy.json) prove that:

1. the exact skipped status was preserved;
2. the explicit policy deterministically produced `WARN`;
3. the record remains tamper-evident and replayable offline.

They do not prove that the warning was actionable. The benchmark outcome now
records the opposite: this expected non-required skip did not warrant work or
a merge-decision change.

## Why retain a noisy case

Removing or rewriting the record would hide a product mistake. Keeping it as a
machine-classified noise control gives the suite three useful checks:

- historical evidence still replays without semantic rewriting;
- current low-noise defaults produce `PASS` for the same required-control
  state;
- public proof cannot count this alert as AOS advantage.

## Replay

```bash
aos-workflow-gate verify \
  --input examples/green-but-incomplete-record.json \
  --bundle examples/green-but-incomplete-bundle.json
```

## Boundary

The check was skipped **by design**. This case shows policy-controlled
visibility and a known false-positive mechanism, not a vulnerability, product
utility, security improvement, or return on investment. The evidence remains
`UNSIGNED_NOT_OFFICIAL`.
