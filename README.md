# AOS Workflow Gate

[![CI](https://github.com/RafineriaAI/aos-workflow-gate/actions/workflows/aos-workflow-gate-ci.yml/badge.svg)](https://github.com/RafineriaAI/aos-workflow-gate/actions/workflows/aos-workflow-gate-ci.yml)
[![Release](https://img.shields.io/github/v/release/RafineriaAI/aos-workflow-gate)](https://github.com/RafineriaAI/aos-workflow-gate/releases/latest)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

[English](#english) | [Polski](#polski)

## English

### Do I need this?

AOS adds a small, deterministic check to tools you already use. It answers
three practical questions:

1. **Does this project build and test successfully on my computer?**
2. **When code and tests changed together, would those tests still pass without
   the implementation change?**
3. **Did the GitHub checks that should protect this pull request actually run
   for the same commit you want to merge?**

It returns `PASS`, `WARN`, or `BLOCK`, explains the main problem, and gives
one next step.

**AOS is useful when:**

- you opened an unfamiliar project and do not know its build or test commands;
- a developer or coding agent changed code and tests in the same pull request;
- your team relies on GitHub required checks before merging;
- GitHub looks green, but you want to know whether every required check
  actually ran;
- you need a saved record of what was checked for one specific commit.

**AOS is probably not useful when:**

- you want an AI code reviewer, bug finder, or architecture review;
- the change is only a refactor or performance optimization and your tests are
  not expected to distinguish it;
- your repository has no required GitHub checks and its local commands are
  already obvious;
- you expect a security, compliance, or defect-free certificate.

**AOS is not another AI reviewer.** It reuses your test command and GitHub
checks. Its experimental Change Proof can test whether a supplied verifier is
sensitive to the actual implementation patch; it does not infer business
intent or prove that the code is correct.

AOS is free under Apache-2.0. It requires no account or telemetry and does not
upload source code to RafineriaAI.

### Try it locally

Install the released version, open a terminal in a project directory, and run:

```bash
python -m pip install "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.38.0"
aos-check
```

For conventional Python, Node.js, Go, Rust, Maven, and Gradle projects, AOS
finds declared build and test commands and runs them. It never installs missing
dependencies or invokes a shell.

Example:

```text
AOS Check: WARN

Problem:
No runnable test command was found.

Why it matters:
The project built, but its behavior was not tested.

Affected area:
Project test setup

Next step:
Add one test for the main user flow, then run aos-check again.
```

### Check whether tests prove a change (experimental)

For a pull request that changes implementation and tests, add AOS after the
existing targeted test command:

```bash
aos-workflow-gate prove-change \
  --base origin/main \
  --repository OWNER/REPO \
  -- \
  python -m pytest tests/changed_area -q
```

AOS keeps the pull request's tests, removes the selected implementation patch
in disposable worktrees, and runs the same command again. `PASS` means the
verifier noticed the missing implementation; `WARN` means it did not. Use a
fast targeted command because AOS runs it three times. Skip this check by
default for behavior-preserving refactors and performance-only changes.

### Check a public pull request

You can inspect a public pull request without changing its repository:

```bash
aos-workflow-gate check-pr https://github.com/OWNER/REPO/pull/NUMBER
```

This checks the current GitHub rules and the workflow results attached to the
pull request's current commit.

### Add it to GitHub

```yaml
name: AOS Check
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

No policy file or manual check list is needed for the first run. The Action is
read-only and does not stop a merge unless you explicitly enable enforcement.

<picture>
  <source media="(max-width: 600px)" srcset="docs/assets/readme-contrast-mobile.png">
  <img src="docs/assets/readme-contrast.png" alt="GitHub looks green while AOS explains that a required control did not run">
</picture>

### Read the result

- `PASS`: the checks covered by the current setup passed.
- `WARN`: there is a named gap that needs a conscious decision.
- `BLOCK`: a required condition is missing or failed. It stops the job only
  when enforcement is enabled.

The Action adds a short summary and an HTML report. It also saves JSON files so
the same decision can be checked again later.

### What is actually proven?

The mechanism is well tested: it binds results to one commit, checks file
integrity, and can repeat the same decision offline.

Everyday usefulness has not been independently proven. The GitHub-gate
holdout added 0/10 new actions matching material reviewer findings. A separate
Change Proof experiment worked mechanically on 8/8 cases across five public
repositories: tests distinguished the implementation in 5/5 code-and-test
pull requests, while an uncalibrated run produced noisy warnings for 2/2
behavior-preserving changes. No external warning acceptance, merge-decision
change, retention, or ROI has been observed.

The honest conclusion is: **continue a narrow Change Proof plug-in experiment,
keep the GitHub gate narrow, and do not enable or sell either as general code
review.**

See the [Change Proof plug-in experiment](benchmarks/change-proof-plugin/REPORT.md),
[GitHub-gate benchmark](benchmarks/adaptive-value-calibration/REPORT.md), and
[release maturity](docs/MATURITY.md).

### Contribute to the experiment

Useful contributions include:

- a public pull request where AOS found something GitHub did not make clear;
- a warning that was wrong, obvious, or not worth acting on;
- a simpler message or next step;
- a repository setup that AOS cannot read correctly;
- a small rule tied to a repeated, costly review problem.

Start with [Contributing](CONTRIBUTING.md). The project is open for
experimentation, not presented as production-proven.

## Polski

### Czy to narzędzie jest dla mnie?

AOS jest niewielkim, deterministycznym dodatkiem do narzędzi, których już
używasz. Odpowiada na trzy praktyczne pytania:

1. **Czy projekt buduje się i przechodzi testy na moim komputerze?**
2. **Jeżeli kod i testy zmieniły się razem, czy te testy przestaną przechodzić
   bez nowej implementacji?**
3. **Czy kontrole wymagane na GitHubie naprawdę uruchomiły się dla tego samego
   commita, który ma zostać połączony?**

Wynik to `PASS`, `WARN` albo `BLOCK`. AOS wskazuje główny problem, jego
znaczenie i jedną następną czynność.

**AOS przydaje się, gdy:**

- otwierasz nieznany projekt i nie znasz poleceń budowania ani testowania;
- programista lub agent zmienił kod i testy w jednym pull requeście;
- zespół polega na kontrolach wymaganych przed połączeniem pull requestu;
- GitHub wygląda na zielony, ale nie masz pewności, czy wszystkie wymagane
  kontrole rzeczywiście się wykonały;
- potrzebujesz zapisu tego, co sprawdzono dla konkretnego commita.

**AOS prawdopodobnie niewiele wniesie, gdy:**

- szukasz recenzji kodu, wykrywania błędów albo oceny architektury;
- zmiana jest wyłącznie refaktorem lub optymalizacją, której test funkcjonalny
  nie powinien rozróżniać;
- repozytorium nie używa wymaganych kontroli GitHuba, a lokalne polecenia są
  oczywiste;
- oczekujesz certyfikatu bezpieczeństwa, zgodności albo braku błędów.

**AOS nie jest kolejnym recenzentem AI.** Korzysta z istniejącego polecenia
testowego i kontroli GitHuba. Eksperymentalny Change Proof sprawdza, czy podany
test reaguje na brak właściwej zmiany w implementacji; nie odgaduje intencji
biznesowej i nie potwierdza poprawności kodu.

Narzędzie jest bezpłatne i dostępne na licencji Apache-2.0. Nie wymaga konta
ani telemetryki i nie wysyła kodu źródłowego do RafineriaAI.

### Sprawdź projekt lokalnie

W katalogu projektu wykonaj:

```bash
python -m pip install "git+https://github.com/RafineriaAI/aos-workflow-gate@v0.38.0"
aos-check
```

AOS rozpoznaje typowe projekty Python, Node.js, Go, Rust, Maven i Gradle.
Uruchamia polecenia zapisane w projekcie. Nie instaluje brakujących zależności
ani nie korzysta z powłoki systemowej.

### Sprawdź, czy testy potwierdzają zmianę (eksperymentalne)

Gdy pull request zmienia implementację i testy, użyj
[polecenia pokazanego wyżej](#check-whether-tests-prove-a-change-experimental) po
istniejącym, celowanym teście. AOS pozostawia nowe testy, tymczasowo usuwa
zmianę implementacji i ponownie uruchamia to samo polecenie. Używaj szybkiego
testu, ponieważ zostanie wykonany trzy razy. Domyślnie pomijaj refaktory i
zmiany wyłącznie wydajnościowe.

### Sprawdź publiczny pull request

```bash
aos-workflow-gate check-pr https://github.com/OWNER/REPO/pull/NUMBER
```

Polecenie niczego nie zmienia w badanym repozytorium. Odczytuje aktualne reguły
GitHuba i wyniki workflow przypisane do bieżącego commita pull requestu.

### Dodaj do GitHuba

Użyj [workflow pokazanego wyżej](#add-it-to-github). Przy pierwszym
uruchomieniu nie trzeba tworzyć pliku z regułami ani ręcznej listy kontroli.
Domyślnie AOS tylko raportuje wynik i nie blokuje połączenia zmian.

### Jak czytać wynik?

- `PASS`: kontrole objęte obecną konfiguracją przeszły.
- `WARN`: pozostał konkretny problem wymagający świadomej decyzji.
- `BLOCK`: brakuje wymaganego warunku albo kontrola zakończyła się błędem.
  Zadanie zostanie zatrzymane tylko po włączeniu trybu wymuszającego.

Podsumowanie pojawia się w GitHub Actions. Dołączony raport HTML pokazuje
problem, znaczenie i następny krok bez konieczności czytania plików JSON.

### Co rzeczywiście potwierdzono?

Mechanizm jest dobrze przetestowany: wiąże wynik z konkretnym commitem,
sprawdza integralność plików i potrafi ponownie wydać tę samą decyzję offline.

Nie potwierdzono jeszcze codziennej użyteczności dla niezależnych
użytkowników. Benchmark bramki GitHuba nie wskazał nowej czynności w 10
realnych pull requestach. Osobny eksperyment Change Proof zadziałał technicznie
w 8/8 przypadków z pięciu repozytoriów: w 5/5 zmian kodu i testów testy
odróżniły nową implementację, ale bez kalibracji AOS ostrzegł także przy 2/2
zmianach zachowujących dotychczasowe działanie. Nie zmierzono jeszcze akceptacji
ostrzeżeń, zmiany decyzji o merge, retencji ani ROI.

Wniosek: **warto dalej testować Change Proof jako wąski dodatek do testów i
utrzymać bramkę GitHuba w ograniczonym zakresie. Nie należy jeszcze włączać ich
domyślnie ani sprzedawać jako ogólnej recenzji kodu.**

Zobacz [eksperyment Change Proof](benchmarks/change-proof-plugin/REPORT.md),
[benchmark bramki GitHuba](benchmarks/adaptive-value-calibration/REPORT.md) oraz
[poziom dojrzałości](docs/MATURITY.md).

### Jak pomóc?

Najbardziej wartościowe są:

- przypadek, w którym AOS pokazał coś, czego GitHub nie wyjaśnił;
- błędne, oczywiste albo nieistotne ostrzeżenie;
- prostszy komunikat lub lepsza następna czynność;
- konfiguracja repozytorium, której AOS nie potrafi poprawnie odczytać;
- mała reguła odpowiadająca powtarzalnemu i kosztownemu problemowi z review.

Instrukcja znajduje się w [Contributing](CONTRIBUTING.md).

## More details / Więcej informacji

- First use / Pierwsze użycie: [User FAQ](docs/USER_FAQ.md)
- Test sensitivity / Czułość testów: [Change Proof](docs/CHANGE_PROOF.md)
- Decide whether to keep it / Decyzja o wdrożeniu: [Adoption Guide](docs/ADOPTION_GUIDE.md)
- GitHub setup: [CI Integrations](docs/CI_INTEGRATIONS.md)
- Optional rules: [Policy Packs](docs/POLICY_PACKS.md)
- Privacy and limits: [Trust](docs/TRUST.md), [Scope](docs/SCOPE.md)
- Standards: [Compatibility](docs/STANDARDS_COMPATIBILITY.md)
- Development: [Development Guide](docs/DEVELOPMENT.md)

## Local development / Rozwój lokalny

```bash
python -m ruff check .
python -m mypy
python -m pytest
python tools/check_public_surface.py
```

## License / Licencja

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
