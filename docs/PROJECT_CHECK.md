# Local Project Check

Status: released as an experimental, free advisory surface in `v0.38.0`.

`aos-check` is the beginner-facing AOS entry point. It checks a folder without
requiring Git, GitHub, a pull request, policy configuration, or knowledge of
the project's test commands.

## Product job

> Tell me whether the project passes its checks, whether a high-confidence
> sharing blocker is present, what was not verified, and what I should do next.

This is intentionally narrower than "prove my app is correct." The command
must earn broader claims through browser-level and external usability testing.

## First run

Install the immutable release:

```bash
python -m pip install "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.38.0"
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

The adapter reads conventional metadata at the selected root. When no
behavioral test is runnable there, it inspects at most eight nested project
roots within four directory levels and runs each command in its own directory:

| Project | Discovered checks |
| --- | --- |
| Python | `compileall`; pytest when tests/configuration are present |
| Node.js | declared `build`, `typecheck`, `test`, and `lint` scripts |
| Go | `go test ./...` |
| Rust | `cargo test --quiet` |
| Maven | `mvn test -q` |
| Gradle | wrapper `test --quiet` |

Every run also performs a bounded internal scan for paired unresolved-conflict
markers and complete private-key blocks. It records finding type, relative
path, and line only; matched source text is never retained.

No dependency is installed automatically. A missing runtime, malformed
manifest, absent test command, incomplete nested discovery or snapshot, timeout, or
launch failure prevents an unqualified `PASS`.

## Decision semantics

| Observation | Verdict | Default exit |
| --- | --- | --- |
| Safety scan and every discovered check pass; at least one behavioral test ran | `PASS` | `0` |
| Paired conflict markers or complete private-key material found | `BLOCK` | `0` |
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
project-state.json
bundle.json
policy.json
gate-decision.json
```

The source identity binds the detected ecosystems, a content digest over
bounded code, configuration, and manifest files; detected project roots;
selected working directories and commands; safety-finding metadata; execution
states; timings; and output digests. It contains no raw command output,
absolute project path, source content, credential value, telemetry, or Git
identifier.

`project-state.json` stores relative paths, content hashes, and unresolved
finding metadata, but no matched content. The first run scans the bounded
snapshot; a later run scans files whose hashes changed and revalidates prior
findings. Malformed, foreign-project, or missing state falls back to a full
scan.

## Security boundary

- AOS invokes known executable argument arrays with `shell=False`.
- Node package scripts and build/test tools execute project code and can have
  arbitrary side effects. Run untrusted projects in an unprivileged sandbox.
- AOS does not install dependencies or contact a service. Project commands may
  use the network according to their own behavior.
- Snapshot hashing is local, skips symlinks and common dependency/build
  directories, and is bounded to 10,000 files and 100 MiB.
- Nested discovery is bounded to eight projects and four directory levels.
- Internal risk scanning reads bounded local text files and retains no matched
  content; it does not validate whether a credential is active.
- No result proves absence of defects, vulnerabilities, or harmful behavior.

## Product boundary

This release reduces first-run friction and makes existing verification
understandable. Nested execution and changed-file risk scanning now add value
beyond invoking one root command, but market differentiation remains
unvalidated. Advancement still requires accepted incremental findings from:

1. browser-level critical-flow verification without test authoring;
2. adversarial tests that reproduce a defect missed by ordinary CI;
3. change-sensitive checks that prove the tests react to the implementation;
4. accepted high-confidence local findings or agent remediation that AOS can
   re-check.

External metrics must include time to first result, actionable rate,
remediation acceptance, incremental findings over ordinary build/test, repeat
use, and false-positive or inconclusive rate.

A frozen 60-repository exact-SHA remeasurement found a declared nested test
command in 8 prior root-only warning cases, 7 with complete bounded discovery.
This demonstrates reduced false-warning risk, not business utility. See the
[committed report](../benchmarks/mass-market/PROJECT_CHECK_REMEASUREMENT.md).
