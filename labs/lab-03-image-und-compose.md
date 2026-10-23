# Lab 3: Image und Compose für den Betrieb

**Ziel:** Du baust das Image für viertelwatt-daten nach den Regeln für den Betrieb und
startest floci, PostgreSQL, die API und den ETL-Job gemeinsam. Das Passwort steht in keiner
Datei, die ins Repository kommt.

**Dauer:** rund 50 Minuten

**Voraussetzung:** Lab 1 und 2 sind fertig, es läuft kein Container namens `floci` mehr
(`docker rm -f floci`). Dockerfile und Compose kennst du aus dem bisherigen Kurs. Neu ist,
worauf es im Betrieb ankommt.

## Teil A: Das Image

### 1. Einen Branch anlegen

```bash
cd ~/viertelwatt-daten
git switch main && git pull
git switch -c betrieb
```

### 2. Das Dockerfile

Lege im Hauptordner die Datei `Dockerfile` an:

```dockerfile
FROM python:3.14-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN useradd --uid 10001 --no-create-home app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY viertelwatt/ viertelwatt/
ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION

USER 10001
EXPOSE 8000

CMD ["uvicorn", "viertelwatt.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

| Regel für den Betrieb | Wo im Dockerfile |
|---|---|
| Feste Version statt `latest` | `python:3.14-slim-trixie` |
| Nicht als root laufen | `useradd` und `USER 10001`. Die Nummer, damit Kubernetes es prüfen kann |
| Abhängigkeiten vor dem Code | `COPY requirements.txt` und `pip install` stehen vor `COPY viertelwatt/`. So bleibt die langsame Installation im Cache |
| Version beim Bauen mitgeben | `ARG APP_VERSION`, die API zeigt sie unter `/version` |
| Kein Passwort im Image | Es gibt keine Zeile mit Zugangsdaten. Die kommen beim Start aus der Umgebung |

### 3. Die `.dockerignore`

```text
.git
.github
.env
.venv
**/__pycache__
**/*.pyc
**/.pytest_cache
daten
daten-fehlerhaft
tests
labs
stoerungen
vorlagen
werkzeuge
iam
lambda
terraform
k8s
.devcontainer
```

Sie hält `.env` und alles, was die Anwendung nicht braucht, aus dem Image heraus.

### 4. Bauen und prüfen

```bash
docker build -t viertelwatt-daten:dev .
docker images viertelwatt-daten
docker run --rm viertelwatt-daten:dev id
```

Kontrolle: Das Image ist da, `id` zeigt `uid=10001(app)`. Nicht `root`. Die Warnung von pip,
dass es als `root` läuft, ist beim Bauen normal: Installiert wird als root, gestartet als `app`.

### 5. Den Cache beobachten

Ändere in `viertelwatt/api.py` den Titel `title="viertelwatt-daten"` in
`title="viertelwatt-daten (Lab 3)"`. Dann:

```bash
docker build -t viertelwatt-daten:dev .
```

Kontrolle: Die Schritte bis einschließlich `pip install` zeigen `CACHED`. Erst ab
`COPY viertelwatt/` wird neu gebaut, der Bau dauert wenige Sekunden.

## Teil B: Der Verbund

### 6. Das Geheimnis in `.env`

```bash
cp .env.example .env
nano .env
```

Setze ein eigenes Passwort, **nur aus Buchstaben, Ziffern und Bindestrichen**, zum Beispiel
`viertelwatt-lab-4711`. Es landet später in einer Adresse der Form
`postgresql://benutzer:passwort@db:5432/...`, Zeichen wie `@ : / # % ?` würden sie zerstören.

```bash
git status
```

Kontrolle: `.env` taucht **nicht** auf, sie steht in `.gitignore`.

> In eurem Fullstack-Projekt stand `POSTGRES_PASSWORD: secret` direkt in der Compose-Datei.
> Liegt die in einem öffentlichen Repository, kennt jede:r das Passwort. Hier steht in der
> Compose-Datei nur der Platzhalter `${POSTGRES_PASSWORD}`, der Wert kommt aus `.env`.

### 7. Die Datei `compose.yaml`

Lege `compose.yaml` im Hauptordner an:

```yaml
services:
  floci:
    image: floci/floci:2.2.0
    ports:
      - "127.0.0.1:4566:4566"
    environment:
      FLOCI_STORAGE_MODE: persistent
      FLOCI_STORAGE_PERSISTENT_PATH: /app/data
      FLOCI_SERVICES_IAM_ENFORCEMENT_ENABLED: ${FLOCI_IAM_PRUEFUNG:-false}
    volumes:
      - floci-daten:/app/data

  db:
    image: postgres:16
    environment:
      POSTGRES_USER: viertelwatt
      POSTGRES_DB: viertelwatt
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD fehlt in .env}
    volumes:
      - db-daten:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -h 127.0.0.1 -U viertelwatt -d viertelwatt"]
      interval: 5s
      timeout: 3s
      retries: 10

  api:
    build: .
    image: viertelwatt-daten:dev
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      DATABASE_URL: postgresql://viertelwatt:${POSTGRES_PASSWORD}@db:5432/viertelwatt
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
      interval: 10s
      timeout: 3s
      retries: 3
    depends_on:
      db:
        condition: service_healthy

  etl:
    build: .
    image: viertelwatt-daten:dev
    command: ["python", "-m", "viertelwatt.etl"]
    environment:
      DATABASE_URL: postgresql://viertelwatt:${POSTGRES_PASSWORD}@db:5432/viertelwatt
      S3_BUCKET: viertelwatt-rohdaten
      S3_PREFIX: rohdaten/
      AWS_ENDPOINT_URL: http://floci:4566
      AWS_DEFAULT_REGION: eu-central-1
      AWS_ACCESS_KEY_ID: ${ETL_ACCESS_KEY_ID:-test}
      AWS_SECRET_ACCESS_KEY: ${ETL_SECRET_ACCESS_KEY:-test}
    depends_on:
      db:
        condition: service_healthy
      floci:
        condition: service_healthy
    profiles: ["job"]

volumes:
  floci-daten:
  db-daten:
```

```bash
docker compose config --quiet && echo "Datei ist gültig"
```

| Teil | Warum so |
|---|---|
| `${POSTGRES_PASSWORD:?...}` | Fehlt der Wert in `.env`, bricht Compose mit dieser Meldung ab, statt mit leerem Passwort zu starten |
| `healthcheck` bei `db` und `api` | Compose weiß, ob ein Dienst wirklich bereit ist, nicht nur, ob er läuft |
| `depends_on` mit `service_healthy` | Die API startet erst, wenn die Datenbank antwortet |
| `profiles: ["job"]` | Der ETL-Job läuft nicht dauernd, sondern nur auf Abruf |
| `volumes` | Daten überleben das Entfernen der Container |

### 8. Starten

```bash
docker compose up -d --build --wait
docker compose ps
curl -s http://localhost:8000/ready
```

Kontrolle: `floci`, `db` und `api` laufen und sind `healthy`. `etl` fehlt, das ist richtig.
`/ready` liefert `{"status":"bereit"}`.

> `--wait` wartet, bis alle Gesundheitsprüfungen grün sind. Ohne diese Angabe kehrt der Befehl
> sofort zurück, und der nächste Schritt kann floci erwischen, bevor es bereit ist.

### 9. Rohdaten hochladen und den ETL-Job starten

Die `export`-Zeilen aus Lab 2 müssen in diesem Terminal gesetzt sein.

```bash
aws s3 mb s3://viertelwatt-rohdaten
aws s3 cp daten/ s3://viertelwatt-rohdaten/rohdaten/ --recursive
docker compose run --rm etl
echo "Exit-Code: $?"
```

Kontrolle: `Angemeldet als arn:aws:iam::000000000000:root`, dann sieben Zeilen
`6528 Zeilen gelesen, 0 verworfen` und `Fertig: 476 Tageswerte gespeichert`, Exit-Code `0`.

> `root` heißt: Der Job nutzt den Generalschlüssel `test` von floci. In Lab 5 bekommt er
> eigene Schlüssel mit wenigen Rechten.

### 10. Ergebnisse abfragen

```bash
curl -s "http://localhost:8000/tageswerte/HOF-V-001?von=2026-10-01&bis=2026-10-03"
curl -s http://localhost:8000/bilanz/2026-10-03
docker compose exec db psql -U viertelwatt -c "SELECT COUNT(*) FROM tageswerte;"
```

Kontrolle: Drei Tageswerte für Zählpunkt `HOF-V-001` der Kundin Hofstrom, eine Bilanz mit
Deckungsgrad, `476` Zeilen in der Tabelle.

### 11. Vorfall 6 nachstellen

```bash
aws s3 cp daten-fehlerhaft/messwerte_2026-06-14.csv s3://viertelwatt-rohdaten/rohdaten/
docker compose run --rm etl
echo "Exit-Code: $?"
aws s3 rm s3://viertelwatt-rohdaten/rohdaten/messwerte_2026-06-14.csv
```

Kontrolle: Eine Zeile `ERROR ... abgelehnt: Dezimalpunkt statt Komma`, Exit-Code `1`. Die
Datei wird nicht still falsch verarbeitet.

### 12. Überleben die Daten?

```bash
docker compose down
docker compose up -d
aws s3 ls s3://viertelwatt-rohdaten/rohdaten/
docker compose exec db psql -U viertelwatt -c "SELECT COUNT(*) FROM tageswerte;"
```

Kontrolle: Bucket und Tabelle sind noch da. Vergleiche mit Schritt 7 in Lab 2.

### 13. Festhalten

```bash
git add Dockerfile .dockerignore compose.yaml viertelwatt/api.py
git commit -m "Image und Compose fuer den Betrieb"
git push -u origin betrieb
gh pr create --fill
gh pr merge --merge --delete-branch
git switch main && git pull
```

Kontrolle: `git show --stat HEAD^2` zeigt vier Dateien, **keine** `.env`.

## Zusatz für Schnelle

- `docker history viertelwatt-daten:dev`: Welche Schicht ist die größte, und warum zeigen
  `ENV`, `USER` und `CMD` `0B`?
- Ändere in `.env` das Passwort, ohne die Volumes zu löschen. Warum kann sich die API danach
  nicht mehr anmelden? (PostgreSQL übernimmt `POSTGRES_PASSWORD` nur beim allerersten Start
  mit leerem Volume.)
- `docker compose down -v` löscht auch die Volumes. Was ist danach weg?
