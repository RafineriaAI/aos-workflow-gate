# User FAQ

First-run answers for operators. Buyer and security-reviewer questions live
in [BUYER_FAQ.md](BUYER_FAQ.md); verification steps in [TRUST.md](TRUST.md).

**Why did my first run say WARN or show few signals?**
Self-Test Mode collects only *completed* check runs, and on a fresh push
your other checks may still be running. Set `wait-for-checks: "120"` with
`required-checks` so the gate polls until the checks that matter have
finished. The gate never waits for "everything" — its own job would never
complete while waiting.

**Why does the summary say the gate "cannot BLOCK yet"?**
Two switches control blocking. `required-checks` decides *what* can block
(a missing or failed required check makes the verdict `BLOCK`), and
`enforce: "true"` decides whether a `BLOCK` verdict *fails the job*. The
summary's Coverage section suggests a starting `required-checks` value
from your detected checks.

**How do I see and keep the evidence?**
The decision record is written to the path in the `record` output
(Self-Test Mode also writes the bundle and generated policy to
`.aos-gate/`). Upload them as artifacts to keep them; on private
repositories treat the record with the same sensitivity as your check
names.

**How do I reproduce a decision locally?**
Download the artifacts, then:

```bash
pip install "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.13.0"
aos-workflow-gate verify --input gate-decision.json --bundle bundle.json
aos-workflow-gate summarize --input gate-decision.json
```

`verify` prints `OK` when the record matches its self-digest and the
bundle; `TAMPERED` means the file changed since the gate wrote it.

## Failure taxonomy

| Symptom | Meaning | Fix |
| --- | --- | --- |
| Exit 0, verdict `PASS` | Policy satisfied. | Nothing. |
| Exit 0, verdict `WARN` | Advisory source not successful; warnings never block. | Review the named source's own report; follow the hint under Reasons. |
| Exit 0, verdict `BLOCK` | Policy would block, but nothing enforces it. | Set `enforce: "true"` (or a blocking policy) if you want the job to fail. |
| Exit 1 after `evaluate` | Policy `BLOCK` under enforcement. | Follow the hints under Reasons: fix or re-run the failed required check, or correct the check name. |
| Exit 1 after `verify` | Record or bundle changed since it was written. | Regenerate from source; investigate the mutation. |
| Exit 2 | Operational error — malformed input, API failure after retries, budget exhausted, policy-digest or context mismatch. No verdict was produced. | Read the error message; it names the operational cause. Never treat it as a policy decision. |
| `missing_required_source` reason | No completed check run with that exact name. | Check the exact name (it must match the check run name), or add `wait-for-checks` so slow checks can finish. |
| Collection status `wait_timeout` | Wait budget ended with required checks still running. | Raise `wait-for-checks`, or accept the fail-closed `BLOCK`. |
| Collection status `truncated` | More check runs existed than the page budget collected. | Raise limits via CLI flags; uncollected required checks fail closed. |

**Does PASS mean my code is safe?**
No. `PASS` means your explicit policy was satisfied by the collected
signals — nothing more. See [SCOPE.md](SCOPE.md) for the claim boundary.
