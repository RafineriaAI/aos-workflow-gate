# User FAQ

First-run answers for operators. Buyer and security-reviewer questions live
in [BUYER_FAQ.md](BUYER_FAQ.md); verification steps in [TRUST.md](TRUST.md).

**Can I use AOS without Git or GitHub?**
Yes. From a `0.38.0` source checkout, install the package, open a terminal in
the project folder, and run `aos-check`. It detects supported root projects
and their conventional checks. No repository, branch, commit, policy, account,
or test-command knowledge is required.

**What does `aos-check` do?**
It runs existing build and behavioral checks for Python, Node.js, Go, Rust,
Maven, or Gradle and shows one result and one next action. It never installs
dependencies. `WARN` commonly means no runnable behavioral test was found;
a quality-only finding is also `WARN`. `BLOCK` means a discovered build, type,
or test check failed. It does not yet test browser flows or prove that the
application meets its intended requirements. See
[Local Project Check](PROJECT_CHECK.md).


**Why did my first run say WARN or show few signals?**
Decision sources contain completed check runs; queued and approval-required
execution remains visible in collection evidence. With automatic GitHub
requirement discovery, the gate stabilizes discovered required controls for
up to 120 seconds by default. A positive `wait-for-checks` value overrides
that budget. With explicit `required-checks`, the default `"0"` performs no
polling, so set a budget when those checks are slow. The gate never waits for
unrequired work or for its own job.

**Why does the summary say the gate "cannot BLOCK yet"?**
Policy decides *what* produces a `BLOCK` verdict. GitHub requirements are
discovered automatically unless explicit `required-checks` replaces them.
Action `mode: "enforce"` decides whether that verdict fails the job; advisory
reports it with exit 0. The Coverage section shows the controls represented in
the evaluated policy.

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
pip install "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.37.1"
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
| `check-project` / `aos-check` | Project result produced; advisory does not fail the process. | Build, type, or test failed under `--mode enforce`. | Invalid folder or operational input; no verdict. |
| `evaluate` / `run` / `check-pr` | Verdict produced; nothing enforced a failure. | Policy `BLOCK` under enforcement. | Operational error; no verdict was produced. |
| `prove-change` | Decision produced; advisory does not fail the process. | Reproducible verifier failure at `HEAD` under `--mode enforce`. | Invalid subject, command, selection, or operational setup; no verdict. |
| `verify` | Record intact. | Record or bundle tampered. | Operational error. |
| `preflight` | Ready — every probed capability responded. | Degraded readiness — a probed capability is unavailable (named by a stable code; **not** a policy verdict). | The probe run itself could not complete. |

Before the first gate run, `preflight` names what the token and target
can actually do (see [PREFLIGHT.md](PREFLIGHT.md) for the diagnostic
code registry):

```bash
aos-workflow-gate preflight --pr https://github.com/OWNER/REPO/pull/N
```

**What does `prove-change` evaluate?**
It runs an explicit verifier at the exact `HEAD`, removes selected
implementation changes in a disposable worktree while retaining the PR tests,
and runs the verifier again. `PASS` means the checks distinguish removal of
the change; `WARN` means they do not or the experiment was inconclusive;
`BLOCK` means the verifier failed twice at `HEAD`. It is not a defect-absence
or correctness claim. See [Executable Change Proof](CHANGE_PROOF.md).

## Failure taxonomy

| Symptom | Meaning | Fix |
| --- | --- | --- |
| Exit 0, verdict `PASS` | Policy satisfied. | Nothing. |
| Exit 0, verdict `WARN` | AOS found a non-blocking merge-control gap. | Read **What AOS found** and perform the single **Next** action. |
| A non-required check failed or skipped, but AOS returned `PASS` | Zero-config records non-required results but does not repeat GitHub-visible failures as AOS warnings. | Use an explicit policy only if that result should affect the AOS verdict. |
| Exit 0, verdict `BLOCK` | Policy found a blocking gap, but Action mode is advisory. | Set `mode: "enforce"` only after measuring noise; a blocking policy also fails the CLI process. |
| Exit 1 after `evaluate` | Policy `BLOCK` under enforcement. | Follow the hints under Reasons: fix or re-run the failed required check, or correct the check name. |
| Exit 1 after `verify` | Record or bundle changed since it was written. | Regenerate from source; investigate the mutation. |
| Exit 2 | Operational error — malformed input, API failure after retries, budget exhausted, policy-digest or context mismatch. No verdict was produced. | Read the error message; it names the operational cause. Never treat it as a policy decision. |
| `missing_required_source` reason | No completed check run with that exact name. | Check the exact name (it must match the check run name), or add `wait-for-checks` so slow checks can finish. |
| Collection status `wait_timeout` | Wait budget ended with required checks still running. | Raise `wait-for-checks`, or accept the fail-closed `BLOCK`. |
| Collection status `truncated` | More check runs existed than the page budget collected. | Raise limits via CLI flags; uncollected required checks fail closed. |
| Collection `unverifiable_required` (check-pr) | A same-named observation exists, but it cannot be shown to satisfy the app-bound requirement (different or unidentifiable app; legacy statuses carry no app identity). | Make the required app report the check, or unbind the requirement in the branch rules; the control fails closed as missing until then. |
| `no_required_sources` reason | GitHub or the explicit policy requires no status check, so green checks enforce nothing. | Configure at least one required status check in GitHub, or pass `required-checks`, then re-run AOS. |
| `incomplete_collection` reason | The bundle records that its collection did not end `complete` (truncated listing or wait timeout), so signals that exist for the commit may be absent — an otherwise-clean result reads `WARN`, never a plain `PASS`. | Re-collect with a larger wait or API budget; set the `incomplete_collection` rule to `BLOCK` in your policy to fail closed instead. |
| Requirement `github_equivalent: would_pass` with state `failed` | The required check concluded `skipped` or `neutral`: GitHub's own semantics count that as passing, but no evidence was actually produced. | Decide which reading you want: make the check actually run, or accept GitHub's formal pass and record the divergence. |
| `non_independent_evidence` reason | This PR changed a workflow that also produced checks used to assess the same PR. | Run or require one check whose workflow definition is unchanged by this PR, then re-run AOS. Acknowledgement records context but does not suppress the reason. |
| `workflow_visibility.not_started` entries | Execution units (check suites) exist on the commit but never produced a check run — `pending` (queued) or `action_required` (awaiting approval, e.g. a fork PR or a deployment gate). They are visible evidence, never a verdict: nothing is `missing` unless something explicitly expected it. | Approve or unblock the listed workflow, or ignore it if it is not part of your policy. |

**Does PASS mean my code is safe?**
No. `PASS` means your explicit policy was satisfied by the collected
signals — nothing more. See [SCOPE.md](SCOPE.md) for the claim boundary.
