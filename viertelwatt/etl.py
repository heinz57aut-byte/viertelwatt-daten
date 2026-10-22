"""ETL-Job: Rohdaten aus S3 lesen, prüfen, summieren, in PostgreSQL schreiben.

Start:  python -m viertelwatt.etl

Der Job läuft einmal und beendet sich. Exit-Code 0 heißt: alles verarbeitet.
Exit-Code 1 heißt: mindestens eine Datei wurde abgelehnt oder es gab einen Fehler.
Kubernetes und Compose werten genau diesen Code aus.
"""

from __future__ import annotations

import logging
import os
import sys

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from viertelwatt import db
from viertelwatt.kern import FormatFehler, lies_csv, tageswerte

log = logging.getLogger("viertelwatt.etl")


def s3_client():
    # AWS_ENDPOINT_URL, Region und Zugangsdaten liest boto3 selbst aus der Umgebung.
    # Ausdrücklich Pfad-Adressierung ("http://floci:4566/<bucket>"). boto3 macht das bei
    # eigenem Endpunkt schon von selbst, so hängt es aber nicht davon ab.
    return boto3.client("s3", config=Config(s3={"addressing_style": "path"}))


def dateien(s3, bucket: str, prefix: str) -> list[str]:
    seiten = s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix)
    return sorted(
        obj["Key"]
        for seite in seiten
        for obj in seite.get("Contents", [])
        if obj["Key"].endswith(".csv")
    )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("botocore").setLevel(logging.WARNING)
    bucket = os.environ.get("S3_BUCKET")
    prefix = os.environ.get("S3_PREFIX", "rohdaten/")
    if not bucket:
        log.error("S3_BUCKET ist nicht gesetzt")
        return 1

    # Unter welcher Identität läuft der Job? Steht hier "root", fehlen die eigenen Schlüssel.
    try:
        arn = boto3.client("sts").get_caller_identity()["Arn"]
        log.info("Angemeldet als %s", arn)
    except (BotoCoreError, ClientError) as fehler:
        log.warning("Identität nicht ermittelbar: %s", fehler)

    s3 = s3_client()
    schluessel = dateien(s3, bucket, prefix)
    log.info("Bucket %s, Ordner %s: %d Dateien gefunden", bucket, prefix, len(schluessel))

    alle = []
    abgelehnt = 0
    for key in schluessel:
        text = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
        try:
            ergebnis = lies_csv(text)
        except FormatFehler as fehler:
            abgelehnt += 1
            log.error("%s abgelehnt: %s", key, fehler)
            continue
        log.info("%s: %d Zeilen gelesen, %d verworfen",
                 key, len(ergebnis.messwerte), len(ergebnis.verworfen))
        for grund in ergebnis.verworfen[:5]:
            log.warning("%s: %s", key, grund)
        alle.extend(ergebnis.messwerte)

    werte = tageswerte(alle)
    with db.verbinden() as conn:
        anzahl = db.speichern(conn, werte)
    log.info("Fertig: %d Tageswerte gespeichert, abgelehnte Dateien: %d", anzahl, abgelehnt)
    return 1 if abgelehnt else 0


if __name__ == "__main__":
    sys.exit(main())
