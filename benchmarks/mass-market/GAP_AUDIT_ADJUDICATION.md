# Missing-test warning adjudication

Status: `CONFIRMED_HIGH_FALSE_POSITIVE_RISK`.

- Candidates: **60**.
- Raw path contradictions: **18/60 (30%)**.
- Definite conventional test surfaces: **12/60 (20%)**.
- Probable validation scripts: **3/60 (5%)**.
- Path-only false matches: **3/18 (16.7%)**.

Even the conservative result exceeds the preregistered maximum contradiction
rate of 10%. The current root-only warning cannot support a low-noise claim.
Before mass exposure it must either discover nested/monorepo test surfaces or
say precisely: "no runnable test command was detected at this project root."

This was a post-hoc, non-blinded, single-evaluator path review. Paths do not
prove that tests are runnable, relevant or passing.

Source result: `sha256:2f29c5fb30fba15188394bfe836bc3981d6a01381a1d155f0ec7e606c867513b`.
