# Lab 4: Pipeline mit GitHub Actions

**Ziel:** Jeder Push startet Tests. Nur wenn sie grün sind, wird ein Image gebaut, auf
Schwachstellen geprüft und in die GitHub Container Registry veröffentlicht.

**Dauer:** rund 40 Minuten

## 1. Die Tests lokal

```bash
git switch main && git pull
git switch -c pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -v
```

Kontrolle: Alle Tests `PASSED`, am Ende `27 passed`. Lies `tests/test_kern.py`: Welcher Test
steht für Vorfall 6?

> Nach `source .venv/bin/activate` heißt der Befehl `python`, davor unter Ubuntu und macOS
> nur `python3`.

## 2. Den Workflow anlegen

```bash
mkdir -p .github/workflows
```

Datei `.github/workflows/ci.yml`:

```yaml
name: ci

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Code holen
        uses: actions/checkout@v7

      - name: Python einrichten
        uses: actions/setup-python@v7
        with:
          python-version: "3.14"
          cache: pip
          cache-dependency-path: requirements*.txt

      - name: Abhaengigkeiten installieren
        run: pip install -r requirements-dev.txt

      - name: Tests
        run: pytest -v

  image:
    needs: test
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - name: Code holen
        uses: actions/checkout@v7

      - name: Image-Namen festlegen
        run: |
          echo "IMAGE=ghcr.io/${GITHUB_REPOSITORY,,}" >> "$GITHUB_ENV"
          echo "TAG=${GITHUB_SHA::7}" >> "$GITHUB_ENV"

      - name: Image bauen
        run: docker build --build-arg APP_VERSION="$TAG" -t "$IMAGE:$TAG" .

      - name: Auf bekannte Schwachstellen pruefen
        run: |
          docker run --rm \
            -v /var/run/docker.sock:/var/run/docker.sock \
            aquasec/trivy:0.75.0@sha256:af6acf9a6b85dfe389a1941505c0ce9efef52a4719635e1a962f022a3d855daa \
            image --severity CRITICAL --ignore-unfixed --exit-code 1 \
            "$IMAGE:$TAG"

      - name: An der Registry anmelden
        if: github.ref == 'refs/heads/main'
        env:
          TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: echo "$TOKEN" | docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin

      - name: Veroeffentlichen
        if: github.ref == 'refs/heads/main'
        run: |
          docker tag "$IMAGE:$TAG" "$IMAGE:latest"
          docker push "$IMAGE:$TAG"
          docker push "$IMAGE:latest"
```

Zwei Stellen sind bewusst so geschrieben:

- Das Trivy-Image hängt nicht nur am Tag `0.75.0`, sondern am **Digest** `@sha256:...`. Ein Tag
  kann der Herausgeber auf anderen Inhalt umhängen, einen Digest nicht. Im März 2026 ist genau
  das bei Trivy passiert, siehe Folie.
- Das Token kommt über `env:` in den Schritt und nicht als `${{ ... }}` direkt in die
  Befehlszeile. So wird es nie Teil eines Skripts, das GitHub zusammensetzt.

## 3. Pull Request: die Pipeline läuft

```bash
git add .github/workflows/ci.yml
git commit -m "Pipeline: Tests, Image, Schwachstellenpruefung"
git push -u origin pipeline
gh pr create --fill
gh pr checks --watch
```

Kontrolle: `test` und `image` werden grün. Die Schritte **An der Registry anmelden** und
**Veroeffentlichen** sind übersprungen, weil das kein Push auf `main` ist.

> Meldet `gh pr checks` `no checks reported`, hat GitHub den Lauf noch nicht angelegt. Ein
> paar Sekunden warten und den Befehl wiederholen. Das gilt auch für alle späteren Labs.

## 4. Einen Fehler einbauen

Du baust jetzt den Fehler aus Vorfall 6 nach: So hat Lenas alte Analyse-Datei gelesen. Ersetze in
`viertelwatt/kern.py` in der Funktion `zahl` die beiden Zeilen

```python
    if "." in t:
        raise FormatFehler(f"Dezimalpunkt statt Komma: {text!r}")
```

durch diese eine Zeile:

```python
    t = t.replace(".", "")  # wie die alte Analyse-Datei: Punkt als Tausendertrenner
```

Probier es lokal aus, bevor du pushst:

```bash
python -c 'from viertelwatt.kern import zahl; print(zahl("0.214"))'
pytest -q
```

Kontrolle: Aus `0.214` wird `214`, genau der Fehler aus dem Juni. `pytest` meldet
`2 failed, 25 passed`.

```bash
git commit -am "Zahlen mit Punkt wie in der alten Analyse-Datei lesen"
git push
gh pr checks --watch
```

Kontrolle: `test` wird **rot**, `image` startet gar nicht. Öffne den Lauf mit
`gh run view --web` und finde den Namen des fehlgeschlagenen Tests.

## 5. Zurücknehmen

```bash
git revert --no-edit HEAD
git push
gh pr checks --watch
```

Kontrolle: Wieder grün. `git log --oneline` zeigt den Fehler **und** seine Rücknahme.
Nichts wurde verschwiegen.

## 6. Mergen und veröffentlichen

```bash
gh pr merge --merge --delete-branch
git switch main && git pull
gh run watch
```

`gh run watch` fragt, welchen Lauf du beobachten willst. Findet es noch keinen, ein paar
Sekunden warten und wiederholen.

Kontrolle: Auf GitHub unter deinem Profil, Reiter **Packages**, liegt `viertelwatt-daten`
mit den Tags `latest` und der kurzen Commit-Kennung.

> Ein neues Paket in der GitHub Container Registry ist **privat**, auch wenn das Repository
> öffentlich ist. Wer es ohne Anmeldung laden soll, braucht unter **Package settings → Change
> visibility** die Einstellung **Public**. Für den Kurs ist das nicht nötig: Am Samstag baust
> du dasselbe Image lokal und lädst es direkt in den Cluster.

## Wenn der Schwachstellen-Schritt rot wird

Dann hat Trivy im Basis-Image eine kritische Lücke gefunden, für die es schon eine
Korrektur gibt. Das ist kein Fehler des Labs, sondern genau der Zweck des Schritts.
Lies in der Ausgabe, welches Paket betroffen ist, und besprich mit dem Trainer, was jetzt
richtig wäre.

## Zusatz für Schnelle

- Schütze `main` auf GitHub: Merge nur mit grünem `test`. Der heutige Weg ist ein Ruleset
  unter **Settings → Rules → Rulesets**, der klassische **Settings → Branches**. Ab dann musst
  du in Lab 5 bis 7 vor `gh pr merge` warten, bis die Prüfung grün ist. Dafür steht dort
  `gh pr checks --watch`.
- Lass das Image zusätzlich mit dem Tag `1.0.0` veröffentlichen, wenn du ein Git-Tag `v1.0.0` pushst.
