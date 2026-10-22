# viertelwatt-daten

Übungsrepository für den Kurs **Cloud & DevOps kompakt** (CODERS.BAY Wien).

Die Viertelwatt GmbH rechnet für Energiegemeinschaften ab. Angefangen hat alles mit einem
Jupyter-Notebook, mit dem Lena Brandl die Viertelstundenwerte ihrer eigenen Gemeinschaft
Hofstrom ausgewertet hat. Hofstrom ist bis heute die erste Kundin, ihre Zählpunkte beginnen
mit `HOF-`. In diesem Kurs bringst du die Auswertung in einen nachvollziehbaren Betrieb: Git,
Container, Pipeline, AWS und Kubernetes.

## Inhalt

| Ordner | Was liegt dort |
|---|---|
| `viertelwatt/` | Die Anwendung: `kern.py` (Fachlogik), `etl.py` (Job), `api.py` (Dienst), `db.py` |
| `tests/` | Tests mit pytest |
| `daten/` | Sieben Tage Beispieldaten im Format des Netzbetreibers |
| `daten-fehlerhaft/` | Eine Datei mit Dezimalpunkt statt Komma (Vorfall 6) |
| `labs/` | Die Übungsanleitungen, Lab 1 bis 7, dazu die Terraform-Vorführung |
| `vorlagen/athena/` | Tabellenbeschreibung für Athena (Lab 6) |
| `vorlagen/lambda/` | Rolle und Zeitplan für die Zusatzaufgabe in Lab 6 |
| `vorlagen/k8s/` | Kubernetes-Manifeste für Lab 7 |
| `stoerungen/` | Vorbereitete Fehler für die Fehlersuche in Kubernetes |
| `werkzeuge/` | Erzeugt weitere Beispieldaten |
| `.devcontainer/` | Einrichtung für GitHub Codespaces |

## Lokal ohne Container ausprobieren

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Unter Ubuntu und macOS heißt der Befehl vor dem Aktivieren `python3`, danach `python`. Die
Tests laufen mit Python 3.12 und 3.14.

## Team

| Name | GitHub |
|---|---|
| | |
