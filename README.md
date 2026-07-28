# AOS Workflow Gate

[![CI](https://github.com/RafineriaAI/aos-workflow-gate/actions/workflows/aos-workflow-gate-ci.yml/badge.svg)](https://github.com/RafineriaAI/aos-workflow-gate/actions/workflows/aos-workflow-gate-ci.yml)
[![Release](https://img.shields.io/github/v/release/RafineriaAI/aos-workflow-gate)](https://github.com/RafineriaAI/aos-workflow-gate/releases/latest)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

[English](#english) | [Polski](#polski)

## English

**AOS finds and runs the project's tests and checks before code review or release. It identifies the main problem and gives you the next step. No Git or test-command knowledge required.**

AOS turns existing project checks and GitHub evidence into a clear
`PASS/WARN/BLOCK` result, the main reason behind it, and a concrete next step.
Locally, it discovers and runs checks already defined by the project. On
GitHub, it checks which required controls ran for the pull request's exact head
commit and whether they produced acceptable results. It is designed for
professional developers, beginners, and people working with coding agents.

**Free to use:** the CLI and GitHub Action are available under Apache-2.0 with
no account, telemetry, paid feature restrictions, or source-code upload to
RafineriaAI.

[`RafineriaAI/aos-kernel`](https://github.com/RafineriaAI/aos-kernel) is the
first-party reference use case. AOS Workflow Gate checks whether declared CI
and release controls produced replayable evidence for the exact kernel
commit. It neither runs the kernel's Lean proof nor claims to prove the kernel
correct.

### Local check

Install the released version pinned to `v0.38.0`:

```bash
python -m pip install "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.38.0"
aos-check
```

```text
AOS Check: WARN

What AOS found:
AOS found no runnable behavioral test command in the scanned scope.

Next:
Add one test for the app's most important user flow, then run aos-check again.
```

AOS recognizes conventional Python, Node.js, Go, Rust, Maven, and Gradle
projects. It can discover up to eight nested projects within four directory
levels and runs their declared build and test commands. On the first run it
scans up to 10,000 files or 100 MiB; later runs rescan changed files and
unresolved findings. The scan detects complete private-key blocks and
unresolved Git merge-conflict marker pairs. AOS does not install dependencies
or invoke a shell.

### GitHub pull-request check

**The GitHub gate verifies controls, not code.** It detects a required control
that is missing, stale, produced by the wrong app, or modified by the same PR.
This is a read-only **pre-merge control assurance** check bound to the exact
head commit and advisory by default.

**Exact commit · Default Action read-only · Advisory by default · No source-code upload**

<picture>
  <source media="(max-width: 600px)" srcset="docs/assets/readme-contrast-mobile.png">
  <img src="docs/assets/readme-contrast.png" alt="GitHub reports clean while AOS warns that required evidence is non-independent">
</picture>

The committed
[`aos-kernel` replay case](docs/case-studies/aos-kernel-release-surface-replay.md)
shows how AOS ties one exact kernel commit to observed workflow signals, the
applied policy, the decision record, and offline replay. The separate
[public-repository corpus](benchmarks/value/EXACT_CONTRAST.md) contains cases
where AOS represents a state that GitHub's standard result does not express.
Neither artifact proves a defect or product efficacy.

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
      - uses: RafineriaAI/aos-workflow-gate@v0.38.0
```

No checkout, manual policy, bundle, or `required-checks` list is needed. The
Action produces a Markdown summary, a replayable JSON decision record, and a
static HTML report. This repository uses the same workflow on its own pull
requests in [CI](.github/workflows/aos-workflow-gate-self.yml).

### Try it on any public PR

```bash
python -m pip install "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.38.0"
aos-workflow-gate check-pr https://github.com/OWNER/REPO/pull/N
```

The command is read-only. Anonymous GitHub API limits may apply.

### Read the result

- `PASS`: collected evidence satisfies every requirement in the selected policy.
- `WARN`: AOS found a named gap, but advisory mode does not stop CI.
- `BLOCK`: the policy classifies the gap as blocking; it stops CI only in
  enforce mode.

The verdict says whether the collected evidence satisfies the policy.
Advisory/enforce mode determines whether a non-`PASS` verdict stops the
process.

### Evidence, trust, and status

```bash
aos-workflow-gate verify --input gate-decision.json --bundle bundle.json
aos-workflow-gate summarize --input gate-decision.json --html --out evidence.html
```

No LLM participates in the verdict path. The default Action is read-only, no
telemetry or account is required, and no source code is uploaded to
RafineriaAI. Records have integrity checks and can be replayed offline, but
they are not signed RafineriaAI attestations (`UNSIGNED_NOT_OFFICIAL`).

Mechanism verification and market validation are separate. Daily usefulness,
alert precision in external teams, retention, incident reduction, and
willingness to pay have not been independently validated. Version `v0.38.0` is
therefore offered as a free advisory preview and is not yet production-proven.
The formal assessment remains [`NO_GO`](benchmarks/value/ASSESSMENT.md) for
efficacy and production-readiness claims. `FREE_SELF_SERVE_VALIDATION` means
anyone can test the tool at no cost. There is no active paid offering.

## Polski

**AOS wykrywa i uruchamia testy oraz inne kontrole projektu przed przeglądem kodu lub publikacją projektu. Wskazuje najważniejszy problem i kolejny krok. Nie musisz znać Gita ani komend testowych.**

AOS zwraca czytelny wynik `PASS/WARN/BLOCK`, główny powód i konkretny następny
krok. Lokalnie wykrywa i uruchamia kontrole zdefiniowane w projekcie. Na
GitHubie sprawdza, które wymagane kontrole zostały wykonane dla dokładnego
commita PR-a i czy dały akceptowany wynik. Jest przeznaczony także dla
początkujących i osób pracujących z agentami AI.

**Dostęp jest bezpłatny:** CLI i GitHub Action są dostępne na licencji
Apache-2.0. Nie wymagają konta, nie wysyłają telemetryki ani kodu do
RafineriaAI, a cała obecna funkcjonalność jest dostępna bez opłat.

Referencyjnym zastosowaniem jest weryfikacja procesu CI i wydania
[`aos-kernel`](https://github.com/RafineriaAI/aos-kernel). AOS sprawdza, czy
zadeklarowane kontrole pozostawiły odtwarzalne dowody dla konkretnego commita.
Nie uruchamia dowodów formalnych kernela w Lean i nie dowodzi poprawności
samego kernela.

### Szybki start

```bash
python -m pip install "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.38.0"
aos-check
```

- Aby sprawdzić publiczny PR: `aos-workflow-gate check-pr <URL>`.
- Aby sprawdzać każdy PR na GitHubie, użyj
  [workflow pokazanego wyżej](#first-value-in-one-pr); domyślnie działa doradczo.

Wynik odpowiada na trzy pytania: co wykonano, czego brakuje i co zrobić dalej.
`PASS` nie oznacza braku błędów. Oznacza, że zebrane dowody spełniają wymagania
wybranej polityki. Werdykt mówi, czy zmiana spełnia te wymagania; tryb
`advisory` lub `enforce` decyduje, czy wynik inny niż `PASS` przerywa proces.

### Praktyczna wartość

- mniej ręcznego sprawdzania, czy wymagane kontrole uruchomiły się dla
  właściwego commita;
- wykrycie wymaganej kontroli, która nie wystartowała lub została wykonana
  przez inną aplikację GitHub niż wymagana;
- lokalna diagnoza bez znajomości komend projektu;
- jedno jasne uzasadnienie, konkretna następna czynność i odtwarzalny zapis
  decyzji.

AOS nie zastępuje przeglądu kodu, testów ani skanerów. Te narzędzia dostarczają
sygnały; AOS stosuje jawne reguły i na ich podstawie ocenia gotowość zmiany w
określonym zakresie. Rzeczywista codzienna użyteczność i trafność alertów nie
zostały jeszcze niezależnie potwierdzone, dlatego `v0.38.0` jest bezpłatną
wersją doradczą do walidacji.

## Documentation / Dokumentacja

- Start / Początek: [User FAQ](docs/USER_FAQ.md), [Preflight](docs/PREFLIGHT.md), and
  [Scope](docs/SCOPE.md).
- Trust / Zaufanie: [Trust](docs/TRUST.md),
  [Security readiness](docs/SECURITY_READINESS.md), and
  [Standards compatibility](docs/STANDARDS_COMPATIBILITY.md).
- Product fit / Dopasowanie produktu: [Value](docs/VALUE.md),
  [Buyer FAQ](docs/BUYER_FAQ.md), and [Comparison](docs/COMPARISON.md).
- Operation / Utrzymanie: [Release governance](docs/RELEASE_GOVERNANCE.md) and
  [Contributing](CONTRIBUTING.md).

## Local development / Rozwój lokalny

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

## License / Licencja

Apache-2.0. See [LICENSE](LICENSE).

The license covers this repository's source code only. It grants no rights to
the "AOS", "AOS Kernel", or "RafineriaAI" names and marks, and no rights to the
separate proprietary AOS Core technology. See [NOTICE](NOTICE).
