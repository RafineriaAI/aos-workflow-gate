# AOS Workflow Gate

[![CI](https://github.com/RafineriaAI/aos-workflow-gate/actions/workflows/aos-workflow-gate-ci.yml/badge.svg)](https://github.com/RafineriaAI/aos-workflow-gate/actions/workflows/aos-workflow-gate-ci.yml)
[![Release](https://img.shields.io/github/v/release/RafineriaAI/aos-workflow-gate)](https://github.com/RafineriaAI/aos-workflow-gate/releases/latest)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

[English](#english) | [Polski](#polski)

## English

**Check your project before you share it. No Git or test expertise required.**

AOS turns existing project checks and GitHub signals into one explainable
`PASS/WARN/BLOCK` decision, one dominant reason, and one next action. It is for
professional developers, beginners, and people building with coding agents.

**Free to use:** the Apache-2.0 CLI and GitHub Action have no feature gate,
account requirement, telemetry, or hosted source-code upload.

The first-party reference target is
[`RafineriaAI/aos-kernel`](https://github.com/RafineriaAI/aos-kernel). AOS
Workflow Gate verifies whether declared workflow and release controls produced
replayable evidence for the exact kernel commit. It does not execute the
kernel's Lean proof or claim a formal kernel guarantee.

### Local check

`aos-check` is a `0.38.0` candidate. Until that tag exists, install it from a
source checkout:

```bash
python -m pip install .
aos-check
```

```text
AOS Check: WARN

What AOS found:
AOS found no runnable behavioral test command in the scanned scope.

Next:
Add one test for the app's most important user flow, then run aos-check again.
```

The bounded local check supports conventional Python, Node.js, Go, Rust, Maven,
and Gradle projects, including nested projects. It runs declared build and test
commands and checks changed files for complete private-key blocks and paired
merge-conflict markers. It does not install dependencies or invoke a shell.

### GitHub pre-merge control assurance

**The GitHub gate verifies controls, not code.** It finds a required control
that is missing, stale, produced by the wrong app, or modified by the same PR.
The decision is bound to the exact head commit and is advisory by default.

**Exact commit · Default Action read-only · Advisory by default · No source-code upload**

<picture>
  <source media="(max-width: 600px)" srcset="docs/assets/readme-contrast-mobile.png">
  <img src="docs/assets/readme-contrast.png" alt="GitHub reports clean while AOS warns that required evidence is non-independent">
</picture>

The committed
[`aos-kernel` replay case](docs/case-studies/aos-kernel-release-surface-replay.md)
binds one kernel commit to collected workflow signals, policy, decision record,
and offline replay. Independent public-repository contrasts remain in the
[auditable research corpus](benchmarks/value/EXACT_CONTRAST.md); they prove a
bounded semantic difference, not a defect or efficacy claim.

### First value in one PR

```yaml
name: AOS Self-Test
on: pull_request

permissions:
  contents: read
  checks: read
  actions: read
  pull-requests: read
  statuses: read

jobs:
  aos:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1
        with:
          python-version: "3.11"
      - uses: RafineriaAI/aos-workflow-gate@v0.37.1
```

No checkout, manual policy, bundle, or `required-checks` list is needed. The
Action produces a Markdown summary and uploads replayable JSON plus static HTML
evidence. This repository dogfoods the same workflow in
[CI](.github/workflows/aos-workflow-gate-self.yml).

### Try it on any public PR

```bash
python -m pip install "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.37.1"
aos-workflow-gate check-pr https://github.com/OWNER/REPO/pull/N
```

The command is read-only. Anonymous GitHub API limits may apply.

### Read the result

- `PASS`: every requirement declared by the selected policy was satisfied.
- `WARN`: a named readiness gap needs attention, but advisory CI continues.
- `BLOCK`: the policy says the gap must block; enforcement is still opt-in.

The verdict and the process exit code are separate. The verdict describes the
decision; advisory/enforce mode controls whether the process stops.

### Evidence, trust, and status

```bash
aos-workflow-gate verify --input gate-decision.json --bundle bundle.json
aos-workflow-gate summarize --input gate-decision.json --html --out evidence.html
```

No LLM participates in the verdict path. The default Action is read-only, no
telemetry or account is required, and no source code is uploaded to
RafineriaAI. Records are tamper-evident and replayable but remain
`UNSIGNED_NOT_OFFICIAL`.

Mechanism verification and market validation are separate. Daily usefulness,
alert precision in external teams, retention, incident reduction, and
willingness to pay are not independently validated. The formal value status is
[`NO_GO`](benchmarks/value/ASSESSMENT.md); `FREE_SELF_SERVE_VALIDATION` permits
the free advisory release while efficacy and production claims remain closed.
There is no active paid offering.

## Polski

**Sprawdź projekt przed udostępnieniem. Bez znajomości Gita i komend testowych.**

AOS uruchamia istniejące kontrole projektu, zbiera sygnały GitHub i zwraca jeden
wyjaśnialny werdykt `PASS/WARN/BLOCK`, główną przyczynę oraz konkretny następny
krok. Narzędzie jest przeznaczone także dla początkujących i osób pracujących z
agentami kodującymi.

**Dostęp jest bezpłatny:** CLI i GitHub Action są wydane na Apache-2.0, bez
konta, telemetryki, blokad funkcji i wysyłania kodu do RafineriaAI.

Pierwszym referencyjnym celem jest operacyjna weryfikacja
[`aos-kernel`](https://github.com/RafineriaAI/aos-kernel): czy zadeklarowane
kontrole workflow i release dostarczyły dowody dla dokładnego commita kernela.
Nie jest to formalny dowód semantyki kernela.

### Szybki start

- Lokalnie: zainstaluj wersję źródłową i uruchom `aos-check`.
- W GitHub: dodaj pokazany wyżej workflow; domyślnie działa tylko doradczo.
- Dla publicznego PR-a: uruchom `aos-workflow-gate check-pr <URL>`.

Wynik odpowiada na trzy pytania: co wykonano, czego brakuje i co zrobić dalej.
`PASS` nie oznacza braku błędów; oznacza wyłącznie spełnienie jawnie
sprawdzonych wymagań. Werdykt nie jest exit code'em: dopiero tryb `enforce`
może przerwać CI.

### Praktyczna wartość

- mniej ręcznego ustalania, które kontrole rzeczywiście objęły zmianę;
- widoczność testu lub kontroli, która nie wystartowała albo pochodzi z
  niewłaściwej aplikacji;
- lokalna diagnoza bez znajomości komend projektu;
- jedno uzasadnienie, następna czynność i odtwarzalny zapis decyzji.

AOS nie zastępuje review, testów ani skanerów. Istniejące narzędzia dostarczają
sygnały; AOS składa je w ograniczoną decyzję gotowości. Użyteczność rynkowa i
niski poziom szumu wymagają nadal walidacji zewnętrznej, dlatego obecne wydanie
jest bezpłatnym, doradczym preview.

## Documentation

- Start: [User FAQ](docs/USER_FAQ.md), [Preflight](docs/PREFLIGHT.md), and
  [Scope](docs/SCOPE.md).
- Trust: [Trust](docs/TRUST.md), [Security readiness](docs/SECURITY_READINESS.md),
  and [Standards compatibility](docs/STANDARDS_COMPATIBILITY.md).
- Product fit: [Value](docs/VALUE.md), [Buyer FAQ](docs/BUYER_FAQ.md), and
  [Comparison](docs/COMPARISON.md).
- Operation: [Release governance](docs/RELEASE_GOVERNANCE.md) and
  [Contributing](CONTRIBUTING.md).

## Local development

Run the local hygiene checks with:

```bash
python -m ruff check .
python -m mypy
python -m pytest
python tools/check_public_surface.py
```

Or run only the public-surface guard:

```bash
python tools/check_public_surface.py
```

## License

Apache-2.0. See [LICENSE](LICENSE).

The license covers this repository's source code only. It grants no rights to
the "AOS", "AOS Kernel", or "RafineriaAI" names and marks, and no rights to the
separate proprietary AOS Core technology. See [NOTICE](NOTICE).
