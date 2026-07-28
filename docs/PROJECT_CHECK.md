# Local Project Check

Status: `0.38.0` candidate. Not present in published `v0.37.1`.

`aos-check` is the beginner-facing AOS entry point. It checks a folder without
requiring Git, GitHub, a pull request, policy configuration, or knowledge of
the project's test commands.

## Product job

> Tell me whether the project passes the checks it already has, what important
> verification is missing, and what I should do next.

This is intentionally narrower than "prove my app is correct." The candidate
must earn broader claims through browser-level and external usability testing.

## First run

From a source checkout:

```bash
python -m pip install .
cd path/to/project
aos-check
```

Use another folder without changing directory:

```bash
aos-check path/to/project
```

`aos-check` is an alias for:

```bash
aos-workflow-gate check-project
```

## Discovery

The v0 adapter reads only conventional root-level metadata:

| Project | Discovered checks |
| --- | --- |
| Python | `compileall`; pytest when tests/configuration are present |
| Node.js | declared `build`, `typecheck`, `test`, and `lint` scripts |
| Go | `go test ./...` |
| Rust | `cargo test --quiet` |
| Maven | `mvn test -q` |
| Gradle | wrapper `test --quiet` |

No dependency is installed automatically. A missing runtime, malformed
manifest, absent behavioral test, incomplete bounded snapshot, timeout, or
launch failure prevents an unqualified `PASS`.

## Decision semantics

| Observation | Verdict | Default exit |
| --- | --- | --- |
| Every discovered check passes and at least one behavioral test ran | `PASS` | `0` |
| No runnable behavioral test or another explicit coverage limitation | `WARN` | `0` |
| A discovered build, test, or type command fails | `BLOCK` | `0` |
| A discovered lint or quality command reports issues | `WARN` | `0` |
| A command times out or cannot launch | `WARN` | `0` |

With `--mode enforce`, only `BLOCK` exits `1`. Invalid operator input exits
`2`. The verdict describes verification; the exit code controls automation.

## Local result

The terminal shows:

- detected project type;
- every executed check and duration;
- one dominant finding;
- one next action;
- a bounded preview of the first failing command.

The failure preview is never written to evidence. It can contain output from
the user's own command and remains local to the terminal session.

## Evidence

The command writes `.aos-check/`:

```text
project-check-source.json
bundle.json
policy.json
gate-decision.json
```

The source identity binds the detected ecosystems, a content digest over
bounded code and manifest files, selected commands, execution states, exit
codes, durations, byte counts, and output digests. It contains no raw command
output, absolute project path, source content, credential, telemetry, or Git
identifier.

## Security boundary

- AOS invokes known executable argument arrays with `shell=False`.
- Node package scripts and build/test tools execute project code and can have
  arbitrary side effects. Run untrusted projects in an unprivileged sandbox.
- AOS does not install dependencies or contact a service. Project commands may
  use the network according to their own behavior.
- Snapshot hashing is local, skips symlinks and common dependency/build
  directories, and is bounded to 10,000 files and 100 MiB.
- No result proves absence of defects, vulnerabilities, or harmful behavior.

## Product boundary

This candidate reduces first-run friction and makes existing verification
understandable. On its own, it is not sufficiently differentiated from build
and test runners. Advancement to a mass product requires validated additional
value from at least one of:

1. browser-level critical-flow verification without test authoring;
2. adversarial tests that reproduce a defect missed by ordinary CI;
3. change-sensitive checks that prove the tests react to the implementation;
4. accepted remediation that a coding agent can apply and AOS can re-check.

External metrics must include time to first result, actionable rate,
remediation acceptance, incremental findings over ordinary build/test, repeat
use, and false-positive or inconclusive rate.
