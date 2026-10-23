# Lab 2: Container und die lokale Cloud

**Ziel:** Du wiederholst kurz die Container-Befehle, die du kennst, mit Blick auf den Betrieb.
Dann startest du floci als lokale AWS-Umgebung und legst die Rohdaten in einen S3-Bucket.

**Dauer:** rund 35 Minuten

**Voraussetzung:** Docker läuft (`docker version` zeigt Client **und** Server), die AWS CLI
ist installiert, du bist im Ordner `viertelwatt-daten`.

## Teil A: Container, was im Betrieb zählt

### 1. Ein Webserver, nur für dich

```bash
docker run -d --name web -p 127.0.0.1:8080:80 nginx:1.30
docker ps
curl -s http://localhost:8080 | head -5
```

Kontrolle: `docker ps` zeigt `web` mit `127.0.0.1:8080->80/tcp`, `curl` liefert HTML.

| Teil | Warum so |
|---|---|
| `127.0.0.1:8080` | nur von deinem Rechner aus erreichbar. Ohne diese Angabe lauscht der Port auf allen Netzwerkschnittstellen, im Kurs-WLAN also für alle |
| `nginx:1.30` | eine feste Version. Ohne Tag nimmt Docker `latest`, und das ist morgen ein anderes Image als heute |

### 2. Hineinschauen und aufräumen

```bash
docker logs web
docker exec web cat /etc/os-release
docker rm -f web
docker images nginx
```

Kontrolle: Im Container läuft ein anderes System als auf deinem Rechner. Nach `docker rm`
ist der Container weg, das Image `nginx:1.30` ist noch da.

> **Merke:** Container weg heißt nicht Image weg. Und Image da heißt nicht Container läuft.

## Teil B: floci als lokale AWS-Umgebung

### 3. floci starten

```bash
docker run -d --name floci -p 127.0.0.1:4566:4566 floci/floci:2.2.0
docker ps
```

Kontrolle: Nach einigen Sekunden zeigt `docker ps` bei `floci` den Status `Up ... (healthy)`.
Das floci-Image bringt eine eigene Gesundheitsprüfung mit. Was floci beim Start ausgibt,
zeigt `docker logs floci`.

### 4. Die AWS CLI auf floci richten

```bash
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_DEFAULT_REGION=eu-central-1
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test

aws sts get-caller-identity
```

Kontrolle: `"Account": "000000000000"`. Zwölf Nullen heißt: Emulator, kein echtes Konto.

> Die `export`-Zeilen gelten nur in diesem Terminal. Für die Kurswoche kannst du sie in
> `~/.bashrc` eintragen. Entferne sie nach dem Kurs wieder, sonst schickt jeder AWS-Befehl auf
> deinem Rechner seine Anfragen an `localhost`. Eine sauberere Lösung mit einem eigenen Profil
> steht in der Befehlsreferenz.

### 5. Einen Bucket anlegen und die Rohdaten hochladen

```bash
aws s3 mb s3://viertelwatt-rohdaten
aws s3 cp daten/ s3://viertelwatt-rohdaten/rohdaten/ --recursive
aws s3 ls s3://viertelwatt-rohdaten/rohdaten/
```

Kontrolle: Sieben Dateien `messwerte_2026-10-01.csv` bis `..._2026-10-07.csv`.

### 6. Eine Datei zurückholen

```bash
aws s3 cp s3://viertelwatt-rohdaten/rohdaten/messwerte_2026-10-03.csv /tmp/probe.csv
head -3 /tmp/probe.csv
```

Kontrolle: Kopfzeile und zwei Messwerte mit Dezimalkomma.

### 7. Was passiert mit den Daten?

```bash
docker rm -fv floci
docker run -d --name floci -p 127.0.0.1:4566:4566 floci/floci:2.2.0
aws s3 ls
```

Kontrolle: Die Liste ist **leer**. Der Bucket ist mit dem Container verschwunden, denn
floci hält ohne weitere Einstellung alles nur im Arbeitsspeicher. Das lösen wir in Lab 3 mit
einem Volume. `-v` bei `docker rm` entfernt auch das unbenannte Volume, das das floci-Image
anlegt.

### 8. Aufräumen

```bash
docker rm -fv floci
```

Wichtig: Lab 3 startet floci über Compose auf demselben Port 4566.

## Zusatz für Schnelle

- `docker stats` zeigt, wie viel Speicher und CPU deine Container gerade brauchen.
- `aws s3 ls s3://viertelwatt-rohdaten/rohdaten/ --human-readable --summarize`: Wie groß sind sieben Tage Rohdaten? Rechne hoch auf 6.000 Zählpunkte und ein Jahr.
