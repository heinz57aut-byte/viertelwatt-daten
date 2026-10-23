# Lab 6: Daten in AWS

**Ziel:** Das Datenbankpasswort zieht aus der Compose-Datei in den AWS Secrets Manager, und
nur der ETL-Job darf es lesen. Dann fragst du die Rohdaten in S3 direkt mit SQL ab, ohne
Datenbank, mit Athena.

**Dauer:** rund 40 Minuten

**Voraussetzung:** Lab 5 ist fertig: Die Rechteprüfung in floci ist eingeschaltet, der
Benutzer `etl-job` und das Profil `etl` existieren. In deinem Terminal sind die
`export`-Zeilen aus Lab 2 gesetzt, du arbeitest also als Verwaltung (`test`).

## Teil A: Das Passwort in den Tresor

### 1. floci darf Hilfscontainer starten

```bash
cd ~/viertelwatt-daten
git switch main && git pull
git switch -c daten-in-aws
```

Ergänze in `compose.yaml` beim Dienst `floci` zwei Angaben:

```yaml
  floci:
    image: floci/floci:2.2.0
    user: root
    ports:
      - "127.0.0.1:4566:4566"
    environment:
      FLOCI_STORAGE_MODE: persistent
      FLOCI_STORAGE_PERSISTENT_PATH: /app/data
      FLOCI_SERVICES_IAM_ENFORCEMENT_ENABLED: ${FLOCI_IAM_PRUEFUNG:-false}
    volumes:
      - floci-daten:/app/data
      - /var/run/docker.sock:/var/run/docker.sock
```

```bash
docker compose up -d --wait floci
```

Kontrolle: `Container viertelwatt-daten-floci-1 Healthy`.

> Athena und Lambda rechnet floci in eigenen Containern. Dafür braucht es Zugriff auf
> Docker, also auf `/var/run/docker.sock`. Wer diese Datei hat, darf auf dem Rechner praktisch
> alles. Für eine Übung auf dem eigenen Rechner ist das vertretbar, für einen Server nicht.

### 2. Das Geheimnis anlegen

```bash
PW=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2)
aws secretsmanager create-secret --name viertelwatt/datenbank \
  --description "Verbindung zur Datenbank fuer den ETL-Job" \
  --secret-string "postgresql://viertelwatt:${PW}@db:5432/viertelwatt"
```

Kontrolle: Die Ausgabe zeigt `ARN` und `Name`. Die ARN endet auf `viertelwatt/datenbank-`
und sechs zufällige Zeichen. Die hängt AWS an, damit ein gelöschtes und neu angelegtes
Geheimnis gleichen Namens nicht dieselbe Adresse bekommt.

| Teil | Was passiert |
|---|---|
| `PW=$(grep … \| cut -d= -f2)` | holt das Passwort aus `.env` in eine Variable dieses Terminals, ohne es anzuzeigen |
| `--name viertelwatt/datenbank` | der Schrägstrich ordnet Geheimnisse wie in Ordnern |
| `--secret-string` | der geheime Wert: hier die ganze Datenbankadresse |

### 3. Dem ETL-Job das Lesen erlauben, nur dieses eine Geheimnis

Lege `iam/geheimnis-lesen.json` an:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DatenbankGeheimnisLesen",
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:eu-central-1:000000000000:secret:viertelwatt/datenbank-*"
    }
  ]
}
```

```bash
aws iam put-user-policy --user-name etl-job \
  --policy-name geheimnis-lesen \
  --policy-document file://iam/geheimnis-lesen.json
aws iam list-user-policies --user-name etl-job
```

Kontrolle: Zwei Richtlinien, `rohdaten-lesen` aus Lab 5 und `geheimnis-lesen`.

> Das `-*` am Ende steht für die sechs zufälligen Zeichen der ARN. Ohne Sternchen passt die
> Richtlinie im echten AWS auf kein Geheimnis.

### 4. Der ETL-Job liest aus dem Tresor

Trage die ARN aus Schritt 2 in `.env` ein:

```bash
ARN=$(aws secretsmanager describe-secret --secret-id viertelwatt/datenbank --query ARN --output text)
echo "DATENBANK_GEHEIMNIS=$ARN" >> .env
```

Ersetze in `compose.yaml` beim Dienst `etl` die Zeile mit `DATABASE_URL` durch:

```yaml
      DATABASE_SECRET_ID: ${DATENBANK_GEHEIMNIS:?DATENBANK_GEHEIMNIS fehlt in .env}
```

```bash
docker compose run --rm etl
grep -n POSTGRES_PASSWORD compose.yaml
```

Kontrolle: `Angemeldet als ...user/etl-job`, danach `Fertig: 476 Tageswerte gespeichert`.
`grep` findet `POSTGRES_PASSWORD` nur noch bei `db` und `api`, nicht mehr beim ETL-Job. Der Job
kennt das Passwort erst zur Laufzeit, aus dem Tresor.

> Woher weiß die Anwendung, was zu tun ist? `viertelwatt/db.py` nimmt `DATABASE_URL`, wenn sie
> gesetzt ist, sonst `DATABASE_SECRET_ID` und fragt damit den Secrets Manager.

### 5. Nachweisen, was der ETL-Job darf

```bash
aws secretsmanager create-secret --name viertelwatt/anderes --secret-string geheim
env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY bash
export AWS_PROFILE=etl
ARN=$(grep '^DATENBANK_GEHEIMNIS=' .env | cut -d= -f2)
aws secretsmanager get-secret-value --secret-id "$ARN" --query Name   # erlaubt
aws secretsmanager get-secret-value --secret-id viertelwatt/anderes  # AccessDenied
aws secretsmanager list-secrets                                      # AccessDenied
exit
```

Kontrolle: Nur das eigene Geheimnis ist lesbar. Auflisten und fremde Geheimnisse enden mit
`AccessDeniedException`.

> Frag im Lab mit der ARN, nicht mit dem Namen. floci 2.2.0 vergleicht bei einer Abfrage über
> den Namen ohne die zufällige Endung und verweigert dann auch das eigene Geheimnis. Im echten
> AWS gehen beide Wege.

## Teil B: SQL direkt auf die Rohdaten

### 6. Eine Tabelle über die Rohdaten legen

Athena liest Dateien in S3, als wären sie eine Tabelle. Welche Spalten es gibt und wo die
Dateien liegen, steht im Datenkatalog AWS Glue. Die Beschreibung liegt vorbereitet im Repo:

```bash
cat vorlagen/athena/messwerte-tabelle.json
aws glue create-database --database-input Name=viertelwatt
aws glue create-table --database-name viertelwatt \
  --table-input file://vorlagen/athena/messwerte-tabelle.json
aws glue get-tables --database-name viertelwatt --query 'TableList[].Name'
```

Kontrolle: `["messwerte"]`. Lies in der Vorlage: Wo liegen die Dateien, welches
Trennzeichen, warum wird die erste Zeile übersprungen?

### 7. Die erste Abfrage

Athena arbeitet **asynchron**: Du gibst eine Abfrage ab, bekommst eine Kennung und holst
das Ergebnis später.

```bash
ABFRAGE=$(aws athena start-query-execution \
  --query-string "SELECT COUNT(*) AS zeilen FROM viertelwatt.messwerte" \
  --result-configuration OutputLocation=s3://viertelwatt-rohdaten/athena-ergebnisse/ \
  --query QueryExecutionId --output text)
aws athena get-query-execution --query-execution-id "$ABFRAGE" \
  --query QueryExecution.Status.State
aws athena get-query-results --query-execution-id "$ABFRAGE" \
  --query 'ResultSet.Rows[].Data[].VarCharValue' --output text
```

Kontrolle: Der Zustand ist `SUCCEEDED` (bei `RUNNING` ein paar Sekunden warten und noch
einmal fragen), das Ergebnis `45696`. Das sind sieben Dateien mit je 6528 Zeilen.

### 8. Wer hat am 3. Oktober am meisten bezogen?

```bash
ABFRAGE=$(aws athena start-query-execution --query-string "
  SELECT zaehlpunkt,
         ROUND(SUM(CAST(REPLACE(CAST(kwh AS VARCHAR), ',', '.') AS DOUBLE)), 3) AS bezug_kwh
  FROM viertelwatt.messwerte
  WHERE richtung = 'BEZUG' AND CAST(zeitpunkt AS VARCHAR) LIKE '2026-10-03%'
  GROUP BY zaehlpunkt
  ORDER BY bezug_kwh DESC
  LIMIT 5" \
  --result-configuration OutputLocation=s3://viertelwatt-rohdaten/athena-ergebnisse/ \
  --query QueryExecutionId --output text)
sleep 5
aws athena get-query-results --query-execution-id "$ABFRAGE" \
  --query 'ResultSet.Rows[].Data[].VarCharValue' --output text
curl -s "http://localhost:8000/tageswerte/HOF-V-064?von=2026-10-03&bis=2026-10-03"
```

Kontrolle: Ganz vorne steht `HOF-V-064` mit `155.434`, und die API meldet für denselben Tag
`"bezug_kwh":155.434`. Zwei Wege, ein Ergebnis: Athena rechnet direkt aus den Rohdaten, die
API aus der Datenbank, die der ETL-Job befüllt hat.

| Teil der Abfrage | Warum |
|---|---|
| `REPLACE(…, ',', '.')` | Der Netzbetreiber schreibt Dezimalkomma, SQL rechnet mit Punkt |
| `CAST(… AS DOUBLE)` | aus Text wird eine Zahl |
| `CAST(… AS VARCHAR)` | floci erkennt manche Spalten selbst als Zahl oder Zeitpunkt. Die ausdrückliche Umwandlung macht die Abfrage in floci und im echten Athena gleich |

### 9. Festhalten

```bash
git add iam/geheimnis-lesen.json compose.yaml
git commit -m "Datenbankgeheimnis im Secrets Manager, Lesen nur fuer den ETL-Job"
git push -u origin daten-in-aws && gh pr create --fill
gh pr checks --watch
gh pr merge --merge --delete-branch
git switch main && git pull
```

Kontrolle: `git show HEAD^2` zeigt die Richtlinie und die geänderte `compose.yaml`, aber
weder Passwort noch ARN. Die stehen nur in `.env`.

## Zusatz für Schnelle: ein Zeitplan ohne eigenen Server

Der Monatsabschluss soll am 1. jedes Monats um 06:00 Wiener Zeit angestoßen werden, ohne dass
dafür ein Server läuft. Das ist dieselbe Idee wie ein Zeitplan in Airflow oder der
Schedule-Trigger in n8n, nur als AWS-Dienst.

Lege `lambda/monatsabschluss.py` an:

```python
from datetime import datetime, timezone


def handler(event, context):
    jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"Monatsabschluss angestossen um {jetzt}, Auftrag: {event}")
    return {"status": "angestossen", "zeit": jetzt}
```

Die Rolle, mit der Lambda und Scheduler arbeiten, und die Funktion selbst:

```bash
cd lambda && python3 -c "import zipfile; z=zipfile.ZipFile('monatsabschluss.zip','w'); z.write('monatsabschluss.py'); z.close()" && cd ..
aws iam create-role --role-name monatsabschluss \
  --assume-role-policy-document file://vorlagen/lambda/vertrauen.json
aws iam put-role-policy --role-name monatsabschluss --policy-name lambda-aufrufen \
  --policy-document file://vorlagen/lambda/lambda-aufrufen.json
aws lambda create-function --function-name monatsabschluss --runtime python3.12 \
  --handler monatsabschluss.handler --zip-file fileb://lambda/monatsabschluss.zip \
  --role arn:aws:iam::000000000000:role/monatsabschluss
aws lambda wait function-active-v2 --function-name monatsabschluss
aws lambda invoke --function-name monatsabschluss --cli-binary-format raw-in-base64-out \
  --payload '{"monat":"2026-10"}' /tmp/antwort.json && cat /tmp/antwort.json
```

Kontrolle: `"StatusCode": 200` und `{"status": "angestossen", ...}`.

Zwei Zeitpläne, einer für den Betrieb und einer zum Zusehen:

```bash
aws scheduler create-schedule --name monatsabschluss \
  --schedule-expression "cron(0 6 1 * ? *)" --schedule-expression-timezone Europe/Vienna \
  --flexible-time-window Mode=OFF --target file://vorlagen/lambda/zeitplan-ziel.json
aws scheduler create-schedule --name monatsabschluss-test \
  --schedule-expression "rate(1 minute)" \
  --flexible-time-window Mode=OFF --target file://vorlagen/lambda/zeitplan-ziel.json
```

Nach rund zwei Minuten:

```bash
aws logs filter-log-events --log-group-name /aws/lambda/monatsabschluss \
  --query 'events[].message' --output text
aws scheduler delete-schedule --name monatsabschluss-test
```

Kontrolle: Neben deinem Aufruf von Hand stehen ein oder zwei Läufe mit
`Auftrag: {'monat': 'laufend'}`. Die hat der Zeitplan ausgelöst. Der erste Lauf kommt etwa
eine Minute nach dem Anlegen.

> floci startet die Funktion in einem eigenen Container `floci-aws-monatsabschluss-...`. Er
> bleibt stehen, auch wenn du floci beendest. Aufräumen:
> `docker rm -f $(docker ps -aq --filter name=floci-aws-)`
