"""Zugriff auf PostgreSQL.

Die Verbindungsadresse kommt aus der Umgebung, nie aus dem Code:
- DATABASE_URL: die Adresse selbst (Lab 3), oder
- DATABASE_SECRET_ID: Name eines Geheimnisses im AWS Secrets Manager, das die Adresse
  enthält (Lab 6). Dann steht das Passwort in keiner Datei mehr.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

import psycopg

from viertelwatt.kern import Tageswert

SCHEMA = """
CREATE TABLE IF NOT EXISTS tageswerte (
    zaehlpunkt       TEXT          NOT NULL,
    datum            DATE          NOT NULL,
    bezug_kwh        NUMERIC(12,3) NOT NULL,
    einspeisung_kwh  NUMERIC(12,3) NOT NULL,
    PRIMARY KEY (zaehlpunkt, datum)
)
"""

# Wiederholt ausführbar: Ein zweiter Lauf über dieselbe Datei überschreibt,
# statt doppelt zu zählen.
SPEICHERN = """
INSERT INTO tageswerte (zaehlpunkt, datum, bezug_kwh, einspeisung_kwh)
VALUES (%s, %s, %s, %s)
ON CONFLICT (zaehlpunkt, datum) DO UPDATE
SET bezug_kwh = EXCLUDED.bezug_kwh,
    einspeisung_kwh = EXCLUDED.einspeisung_kwh
"""


# Die Tabelle wird je Prozess einmal angelegt, nicht bei jeder Anfrage.
_schema_angelegt = False


def datenbank_url() -> str:
    """Adresse der Datenbank: direkt aus DATABASE_URL oder aus dem Secrets Manager."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    geheimnis = os.environ.get("DATABASE_SECRET_ID")
    if geheimnis:
        import boto3  # erst hier: die API braucht boto3 nur in diesem Fall

        antwort = boto3.client("secretsmanager").get_secret_value(SecretId=geheimnis)
        return antwort["SecretString"]
    raise RuntimeError("Weder DATABASE_URL noch DATABASE_SECRET_ID ist gesetzt")


def verbinden() -> psycopg.Connection:
    global _schema_angelegt
    conn = psycopg.connect(datenbank_url(), connect_timeout=5)
    if not _schema_angelegt:
        with conn.cursor() as cur:
            # Starten zwei Pods gleichzeitig, wartet der zweite hier auf den ersten.
            cur.execute("SELECT pg_advisory_xact_lock(4711)")
            cur.execute(SCHEMA)
        conn.commit()
        _schema_angelegt = True
    return conn


def speichern(conn: psycopg.Connection, werte: list[Tageswert]) -> int:
    with conn.cursor() as cur:
        cur.executemany(
            SPEICHERN,
            [(w.zaehlpunkt, w.datum, w.bezug_kwh, w.einspeisung_kwh) for w in werte],
        )
    conn.commit()
    return len(werte)


def tageswerte_lesen(conn: psycopg.Connection, zaehlpunkt: str,
                     von: date | None, bis: date | None) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT datum, bezug_kwh, einspeisung_kwh
            FROM tageswerte
            WHERE zaehlpunkt = %s
              AND (%s::date IS NULL OR datum >= %s::date)
              AND (%s::date IS NULL OR datum <= %s::date)
            ORDER BY datum
            """,
            (zaehlpunkt, von, von, bis, bis),
        )
        return cur.fetchall()


def bilanz_lesen(conn: psycopg.Connection, datum: date) -> tuple[Decimal, Decimal, int]:
    """Summe Verbrauch, Summe Erzeugung und Anzahl Zählpunkte für einen Tag."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(SUM(bezug_kwh), 0),
                   COALESCE(SUM(einspeisung_kwh), 0),
                   COUNT(*)
            FROM tageswerte
            WHERE datum = %s
            """,
            (datum,),
        )
        return cur.fetchone()


def letzte_bezuege(conn: psycopg.Connection, zaehlpunkt: str, tage: int = 7) -> list[Decimal]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT bezug_kwh FROM (
                SELECT datum, bezug_kwh FROM tageswerte
                WHERE zaehlpunkt = %s
                ORDER BY datum DESC
                LIMIT %s
            ) AS letzte
            ORDER BY datum
            """,
            (zaehlpunkt, tage),
        )
        return [zeile[0] for zeile in cur.fetchall()]
