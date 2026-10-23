# Lab 5: IAM und geringste Rechte

**Ziel:** Der ETL-Job bekommt einen eigenen IAM-Benutzer, der den Rohdaten-Bucket lesen,
aber nicht verändern darf. Du weist nach, dass die Einschränkung wirkt.

**Dauer:** rund 30 Minuten

**Voraussetzung:** Der Compose-Verbund aus Lab 3 läuft, der Bucket `viertelwatt-rohdaten`
enthält die Rohdaten.

## 1. Die Rechteprüfung in floci einschalten

Ohne diese Einstellung lässt floci jeden Aufruf durch. Ergänze in `.env`:

```text
FLOCI_IAM_PRUEFUNG=true
```

```bash
docker compose up -d --wait floci
docker compose logs floci | grep -i "IAM"
```

Kontrolle: Im Log steht eine Zeile mit `IAM:` und `policy enforcement enabled`. Zwischen den
beiden Teilen können mehrere Leerzeichen stehen.

> In `.env` heißt der Schalter `FLOCI_IAM_PRUEFUNG`. `compose.yaml` reicht ihn an floci als
> `FLOCI_SERVICES_IAM_ENFORCEMENT_ENABLED` weiter. Wirksam ist er nur mit dem Wert `true`.

## 2. Als Verwaltung: Benutzer anlegen

Deine Sitzung arbeitet mit `test`/`test`. Das ist in floci das Konto selbst (root) und darf
alles, auch bei eingeschalteter Prüfung.

```bash
aws iam create-user --user-name etl-job
```

## 3. Die Richtlinie schreiben

Lege `iam/rohdaten-lesen.json` an:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BucketAuflisten",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::viertelwatt-rohdaten"
    },
    {
      "Sid": "RohdatenLesen",
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::viertelwatt-rohdaten/*"
    }
  ]
}
```

Achte auf den Unterschied: `ListBucket` gilt für den Bucket, `GetObject` für die Dateien
darin, deshalb `/*`.

```bash
aws iam put-user-policy --user-name etl-job \
  --policy-name rohdaten-lesen \
  --policy-document file://iam/rohdaten-lesen.json
aws iam list-user-policies --user-name etl-job
```

## 4. Zugangsschlüssel erzeugen

```bash
aws iam create-access-key --user-name etl-job
```

Kontrolle: Die Ausgabe enthält `AccessKeyId` und `SecretAccessKey`. Trag beide als
Profil ein:

```bash
aws configure set aws_access_key_id <AccessKeyId> --profile etl
aws configure set aws_secret_access_key <SecretAccessKey> --profile etl
```

> Die Umgebungsvariablen `AWS_ACCESS_KEY_ID` und `AWS_SECRET_ACCESS_KEY` haben Vorrang vor
> `AWS_PROFILE` und vor dem Standardprofil. Nur ein ausdrückliches `--profile etl` bei einem
> einzelnen Befehl würde sie übergehen. Damit du das nicht bei jedem Befehl schreiben musst,
> arbeitest du für die nächsten Schritte in einer **eigenen Sitzung** ohne diese Variablen:

```bash
env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY bash
export AWS_PROFILE=etl
aws sts get-caller-identity
```

Kontrolle: Der ARN endet auf `user/etl-job`. Steht dort `root`, oder kommt eine
Fehlermeldung, **nicht weitermachen**: Dann ist ein Schlüssel falsch abgeschrieben. floci
lässt bei eingeschalteter Prüfung auch unbekannte Schlüssel durch, der Nachweis in Schritt 5
wäre dann wertlos.

## 5. Nachweisen, was erlaubt ist und was nicht

```bash
aws s3 ls s3://viertelwatt-rohdaten/rohdaten/                       # erwartet: erlaubt
aws s3 cp s3://viertelwatt-rohdaten/rohdaten/messwerte_2026-10-01.csv /tmp/probe.csv  # erlaubt
echo test | aws s3 cp - s3://viertelwatt-rohdaten/rohdaten/boese.csv # erwartet: AccessDenied
aws s3 rm s3://viertelwatt-rohdaten/rohdaten/messwerte_2026-10-01.csv # erwartet: AccessDenied
aws s3 ls                                                         # erwartet: AccessDenied
exit
```

Kontrolle: Lesen klappt, Schreiben und Löschen enden mit `AccessDenied`. Notiere die genaue
Fehlermeldung.

- Die Meldung nennt die **API-Operation**, etwa `when calling the PutObject operation`. Die
  passende **IAM-Aktion** heißt meist gleich, aber nicht immer: Für `aws s3 ls` ohne Bucket
  ruft die CLI `ListBuckets` auf, die Aktion dazu heißt `s3:ListAllMyBuckets`.
- Das Auflisten aller Buckets verweigert echtes AWS mit `AccessDenied`. floci erlaubt Aufrufe,
  die es keiner Aktion zuordnen kann, und lässt diesen Aufruf je nach Version eventuell durch.
  Das ist eine Lücke des Emulators, kein Fehler deiner Richtlinie.

## 6. Den ETL-Job mit eigenem Schlüssel betreiben

Ergänze in `.env`:

```text
ETL_ACCESS_KEY_ID=<AccessKeyId>
ETL_SECRET_ACCESS_KEY=<SecretAccessKey>
```

Damit ein vergessener Eintrag nicht still auf den Generalschlüssel `test` zurückfällt,
ändere in `compose.yaml` beim Dienst `etl` die beiden Zeilen:

```yaml
      AWS_ACCESS_KEY_ID: ${ETL_ACCESS_KEY_ID:?ETL_ACCESS_KEY_ID fehlt in .env}
      AWS_SECRET_ACCESS_KEY: ${ETL_SECRET_ACCESS_KEY:?ETL_SECRET_ACCESS_KEY fehlt in .env}
```

```bash
docker compose run --rm etl
```

Kontrolle: Die erste Zeile lautet `Angemeldet als arn:aws:iam::000000000000:user/etl-job`,
nicht mehr `root`. Danach läuft der Job wie in Lab 3 durch. Er braucht nicht mehr als Lesen.

## 7. Festhalten

```bash
git switch -c iam
git add iam/rohdaten-lesen.json compose.yaml
git commit -m "IAM: Leserecht fuer den ETL-Job"
git push -u origin iam && gh pr create --fill
gh pr checks --watch
gh pr merge --merge --delete-branch
git switch main && git pull
```

Kontrolle: `git show --stat HEAD^2` zeigt deinen IAM-Commit mit `iam/rohdaten-lesen.json` und
`compose.yaml`, aber **keine** Schlüssel. Die stehen nur in `.env`.

> Nach dem Merge ist `HEAD` der Merge-Commit. Er hat zwei Eltern: `HEAD^1` ist der alte Stand
> von `main`, `HEAD^2` der letzte Commit deines Branches.

## Zusatz für Schnelle

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::000000000000:user/etl-job \
  --action-names s3:GetObject s3:PutObject s3:DeleteObject \
  --resource-arns arn:aws:s3:::viertelwatt-rohdaten/rohdaten/x.csv \
  --query 'EvaluationResults[].[EvalActionName,EvalDecision]' --output table
```

Die Simulation beantwortet die Frage „darf er das?", ohne es auszuprobieren.
