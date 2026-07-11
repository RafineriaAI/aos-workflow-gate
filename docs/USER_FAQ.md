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
The decision record is written to the path in the `record` output;
Self-Test Mode also writes the bundle, the generated policy, and a
static `evidence.html` view to `.aos-gate/`, and uploads all of it as
the `aos-gate-evidence` artifact by default. **GitHub artifacts expire**
(90 days unless your repository configures otherwise), so they are
retention, not permanence: for decisions worth keeping, attach the
files to a release (this repository gates and attaches its own release
evidence that way) or commit the triple. On private repositories treat
the record with the same sensitivity as your check names.

**How do I reproduce a decision locally?**
Download the artifacts, then:

```bash
pip install "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.31.0"
aos-workflow-gate verify --input gate-decision.json --bundle bundle.json
aos-workflow-gate summarize --input gate-decision.json
```

`verify` prints `OK` when the record matches its self-digest and the
bundle; `TAMPERED` means the file changed since the gate wrote it.

**Can I get a shareable evidence page?**
`summarize --input gate-decision.json --html --out evidence.html`
renders a deterministic, self-contained static HTML view of the record
(no scripts, no external assets, no timestamps — the same record always
renders to the same bytes). It is the same diagnosis as the Markdown
summary, only a different view.

## Exit codes by command

Exit codes are stable but command-scoped — the same number answers a
different question per command:

| Command | 0 | 1 | 2 |
| --- | --- | --- | --- |
| `evaluate` / `run` / `check-pr` | Verdict produced; nothing enforced a failure. | Policy `BLOCK` under enforcement. | Operational error; no verdict was produced. |
| `verify` | Record intact. | Record or bundle tampered. | Operational error. |
| `preflight` | Ready — every probed capability responded. | Degraded readiness — a probed capability is unavailable (named by a stable code; **not** a policy verdict). | The probe run itself could not complete. |

Before the first gate run, `preflight` names what the token and target
can actually do (see [PREFLIGHT.md](PREFLIGHT.md) for the diagnostic
code registry):

```bash
aos-workflow-gate preflight --pr https://github.com/OWNER/REPO/pull/N
```

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
| Collection `unverifiable_required` (check-pr) | A same-named observation exists, but it cannot be shown to satisfy the app-bound requirement (different or unidentifiable app; legacy statuses carry no app identity). | Make the required app report the check, or unbind the requirement in the branch rules; the control fails closed as missing until then. |
| `no_required_sources` reason | Nothing is required by the policy, so nothing can block — zero required plus all-green is an honest `WARN`, never a quiet `PASS`. | Name `required-checks`, or rely on zero-config discovery, which reads required checks from branch rules (classic protection included) automatically. |
| `incomplete_collection` reason | The bundle records that its collection did not end `complete` (truncated listing or wait timeout), so signals that exist for the commit may be absent — an otherwise-clean result reads `WARN`, never a plain `PASS`. | Re-collect with a larger wait or API budget; set the `incomplete_collection` rule to `BLOCK` in your policy to fail closed instead. |
| Requirement `github_equivalent: would_pass` with state `failed` | The required check concluded `skipped` or `neutral`: GitHub's own semantics count that as passing, but no evidence was actually produced. | Decide which reading you want: make the check actually run, or accept GitHub's formal pass and record the divergence. |
| `non_independent_evidence` reason | The named checks were produced by a workflow definition this same change modifies. Advisory by default; affected sources are listed in `collection.verifier_change`. | Require evidence from a verifier governed outside the change. `--acknowledge-verifier-change "reason"` records context but never changes the verdict; raise the rule to `BLOCK` only with an independently governed policy. |
| `workflow_visibility.not_started` entries | Execution units (check suites) exist on the commit but never produced a check run — `pending` (queued) or `action_required` (awaiting approval, e.g. a fork PR or a deployment gate). They are visible evidence, never a verdict: nothing is `missing` unless something explicitly expected it. | Approve or unblock the listed workflow, or ignore it if it is not part of your policy. |

**Does PASS mean my code is safe?**
No. `PASS` means your explicit policy was satisfied by the collected
signals — nothing more. See [SCOPE.md](SCOPE.md) for the claim boundary.
