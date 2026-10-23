# Lab 7: Kubernetes als Einblick

**Ziel:** Ein lokaler Cluster mit kind. Darin laufen Datenbank, floci und zwei Kopien der
API, ein gelöschter Pod kommt von selbst wieder, und der ETL-Job läuft als CronJob jede Nacht.

**Dauer:** rund 40 Minuten

**Voraussetzung:** kind ab Version v0.33 und kubectl sind installiert. Stoppe zuerst den
Compose-Verbund, damit Arbeitsspeicher frei wird. Ohne `-v` bleiben seine Daten erhalten:

```bash
cd ~/viertelwatt-daten
docker compose down
docker rm -f $(docker ps -aq --filter name=floci-aws-) 2>/dev/null
kind delete cluster --name probe   # nur falls der Probecluster noch läuft
```

> floci läuft im Cluster mit `enableServiceLinks: false`, siehe `vorlagen/k8s/21-floci.yaml`.
> Ohne diese Zeile legt Kubernetes die Variable `FLOCI_PORT` an, und floci stürzt ab.

> Meldet `kubectl` später `The connection to the server localhost:8080 was refused`, kennt es
> keinen Cluster. Entweder läuft keiner (`kind get clusters`), oder der Kontext fehlt
> (`kubectl config current-context` muss `kind-viertelwatt` zeigen). Mit der API auf Port
> 8080 hat das nichts zu tun.

## 1. Den Cluster anlegen

```bash
kind create cluster --name viertelwatt --wait 90s
kubectl get nodes
kubectl get pods -n kube-system
```

Kontrolle: Ein Knoten `viertelwatt-control-plane` mit `Ready`. In `kube-system` laufen
`etcd`, `kube-apiserver`, `kube-scheduler`, `kube-controller-manager` und `kube-proxy`, die
Architektur von der Folie als laufende Pods.

## 2. Das Image in den Cluster bringen

kind-Knoten sind selbst Container und sehen deine lokalen Images nicht.

```bash
git switch main && git pull
git switch -c kubernetes
docker build --build-arg APP_VERSION=1.0.0 -t viertelwatt-daten:1.0.0 .
kind load docker-image viertelwatt-daten:1.0.0 --name viertelwatt
```

## 3. Namespace und Secret

```bash
mkdir k8s
cat > k8s/00-namespace.yaml <<'YAML'
apiVersion: v1
kind: Namespace
metadata:
  name: viertelwatt
YAML
kubectl apply -f k8s/00-namespace.yaml
```

Wähle ein Passwort **nur aus Buchstaben, Ziffern und Bindestrichen**, wie in Lab 3.

```bash
read -rsp "Datenbankpasswort: " PW; echo
kubectl create secret generic viertelwatt-geheim -n viertelwatt \
  --from-literal=POSTGRES_PASSWORD="$PW" \
  --from-literal=DATABASE_URL="postgresql://viertelwatt:${PW}@db:5432/viertelwatt" \
  --from-literal=AWS_ACCESS_KEY_ID=test \
  --from-literal=AWS_SECRET_ACCESS_KEY=test
kubectl get secret viertelwatt-geheim -n viertelwatt -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d; echo
```

Kontrolle: Die letzte Zeile zeigt dein Passwort im Klartext. Kubernetes speichert Secrets nur
in Base64, und **Base64 ist keine Verschlüsselung**. Wer Secrets lesen darf, kennt das
Passwort. Deshalb gibt es im Betrieb Werkzeuge, die Secrets aus einem Tresor wie dem AWS
Secrets Manager holen.

## 4. Die vorbereiteten Manifeste anwenden

```bash
cp vorlagen/k8s/10-config.yaml vorlagen/k8s/20-db.yaml \
   vorlagen/k8s/21-floci.yaml vorlagen/k8s/30-api.yaml k8s/
kubectl apply -f k8s/
kubectl wait -n viertelwatt --for=condition=Available deployment --all --timeout=180s
kubectl get pods -n viertelwatt
```

Kontrolle: `db`, `floci` und zwei Pods `api-...` sind `Running` und `1/1` bereit.

Lies `k8s/30-api.yaml` und beantworte für dich: Welche `labels` hat der Pod, welchen
`selector` hat der Service, woher kommt `DATABASE_URL`?

## 5. Wer antwortet?

```bash
kubectl run frager -n viertelwatt --rm -i --restart=Never --image=curlimages/curl:8.22.0 -- \
  sh -c 'for i in 1 2 3 4 5 6; do curl -s api/version; echo; done'
```

Kontrolle: Version `1.0.0`, und bei `host` kommen die Namen **beider** API-Pods vor. Der
Service `api` verteilt die Anfragen. Die Verteilung ist zufällig, nicht streng abwechselnd.

## 6. Selbstheilung

```bash
kubectl get pods -n viertelwatt -l app=api
kubectl delete pod -n viertelwatt $(kubectl get pods -n viertelwatt -l app=api -o name | head -1 | cut -d/ -f2)
kubectl get pods -n viertelwatt -l app=api
```

Kontrolle: Sofort ist ein neuer Pod mit anderem Namen da. Das Deployment sorgt dafür, dass
immer zwei laufen.

## 7. Rohdaten ins floci im Cluster bringen

```bash
kubectl port-forward -n viertelwatt svc/floci 4567:4566 > /dev/null &
sleep 2
aws --endpoint-url http://localhost:4567 s3 mb s3://viertelwatt-rohdaten
aws --endpoint-url http://localhost:4567 s3 cp daten/ s3://viertelwatt-rohdaten/rohdaten/ --recursive --quiet
aws --endpoint-url http://localhost:4567 s3 ls s3://viertelwatt-rohdaten/rohdaten/
kill $!
```

Kontrolle: Sieben Dateien. `&` startet die Weiterleitung im Hintergrund, `kill $!` beendet
sie wieder. `$!` ist die Nummer des zuletzt im Hintergrund gestarteten Programms.

## 8. Der ETL-Job als CronJob

```bash
cp vorlagen/k8s/40-etl-cronjob.yaml k8s/
kubectl apply -f k8s/40-etl-cronjob.yaml
kubectl get cronjob -n viertelwatt
```

Kontrolle: `SCHEDULE 30 3 * * *`, `TIMEZONE Europe/Vienna`.

Bis halb vier früh willst du nicht warten. Starte einen Lauf aus der Vorlage:

```bash
kubectl create job -n viertelwatt --from=cronjob/etl etl-jetzt
kubectl wait -n viertelwatt --for=condition=Complete job/etl-jetzt --timeout=120s
kubectl logs -n viertelwatt job/etl-jetzt | tail -2
```

Kontrolle: `Fertig: 476 Tageswerte gespeichert, abgelehnte Dateien: 0`.

| Airflow | Kubernetes | Hier |
|---|---|---|
| DAG mit Zeitplan | CronJob | `etl`, jede Nacht 03:30 Wiener Zeit |
| Task-Lauf | Job, darin ein Pod | `etl-jetzt` |
| Wiederholung bei Fehler | `backoffLimit` | höchstens zwei Wiederholungen |
| Abhängigkeiten zwischen Tasks | gibt es nicht | ein Job, ein Schritt. Für Ketten nimmt man Airflow, auch im Cluster |

> Warum halb vier und nicht zwei Uhr? Bei der Umstellung auf Sommerzeit springt die Uhr in
> Wien von 02:00 auf 03:00. Ein Lauf um 02:00 fiele an diesem Tag aus.

## 9. Festhalten

```bash
git add k8s/
git commit -m "Kubernetes: Namespace, Config, DB, floci, API, CronJob"
git push -u origin kubernetes && gh pr create --fill
gh pr checks --watch
gh pr merge --merge --delete-branch
git switch main && git pull
```

Kontrolle: Kein Secret im Commit. Das Secret entsteht nur über `kubectl create secret`.

## Zusatz für Schnelle

- **Skalieren:** `kubectl scale deployment api -n viertelwatt --replicas=3`, dann
  `kubectl get pods -n viertelwatt -l app=api`. Warum setzt das nächste `kubectl apply -f k8s/`
  wieder auf zwei zurück?
- **Eine Störung finden:** `kubectl apply -f stoerungen/stoerung-a.yaml` und mit
  `kubectl get pods`, `kubectl describe pod`, `kubectl logs` und `kubectl events` die Ursache
  suchen. Danach `kubectl delete -f stoerungen/stoerung-a.yaml`.

## Aufräumen nach dem Kurs

```bash
kind delete cluster --name viertelwatt
docker compose down -v
docker rm -f $(docker ps -aq --filter name=floci-aws-) 2>/dev/null
```
