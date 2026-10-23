"""API für Mitglieder und Vorstand.

Start:  uvicorn viertelwatt.api:app --host 0.0.0.0 --port 8000
Doku:   http://localhost:8000/docs
"""

from __future__ import annotations

import os
import socket
from datetime import date

import psycopg
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException

from viertelwatt import db
from viertelwatt.kern import deckungsgrad, prognose

VERSION = os.environ.get("APP_VERSION", "dev")

app = FastAPI(title="viertelwatt-daten", version=VERSION)


def verbindung():
    try:
        return db.verbinden()
    except (psycopg.OperationalError, RuntimeError, BotoCoreError, ClientError) as fehler:
        raise HTTPException(status_code=503, detail=f"Datenbank nicht erreichbar: {fehler}")


@app.get("/health")
def health():
    """Lebt der Prozess? Prüft bewusst nicht die Datenbank."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Kann der Dienst Anfragen beantworten? Prüft die Datenbank."""
    with verbindung() as conn:
        conn.execute("SELECT 1")
    return {"status": "bereit"}


@app.get("/version")
def version():
    """Version und Name des Containers, der geantwortet hat."""
    return {"version": VERSION, "host": socket.gethostname()}


@app.get("/tageswerte/{zaehlpunkt}")
def tageswerte(zaehlpunkt: str, von: date | None = None, bis: date | None = None):
    with verbindung() as conn:
        zeilen = db.tageswerte_lesen(conn, zaehlpunkt, von, bis)
    if not zeilen:
        raise HTTPException(status_code=404, detail=f"Keine Werte für {zaehlpunkt}")
    return [
        {"datum": d, "bezug_kwh": float(b), "einspeisung_kwh": float(e)}
        for d, b, e in zeilen
    ]


@app.get("/bilanz/{datum}")
def bilanz(datum: date):
    with verbindung() as conn:
        verbrauch, erzeugung, zaehlpunkte = db.bilanz_lesen(conn, datum)
    if zaehlpunkte == 0:
        raise HTTPException(status_code=404, detail=f"Keine Werte für {datum}")
    grad = deckungsgrad(verbrauch, erzeugung)
    return {
        "datum": datum,
        "verbrauch_kwh": float(verbrauch),
        "erzeugung_kwh": float(erzeugung),
        "deckungsgrad_prozent": float(grad) if grad is not None else None,
        "zaehlpunkte": zaehlpunkte,
    }


@app.get("/prognose/{zaehlpunkt}")
def prognose_morgen(zaehlpunkt: str):
    with verbindung() as conn:
        werte = db.letzte_bezuege(conn, zaehlpunkt)
    wert = prognose(werte)
    if wert is None:
        raise HTTPException(status_code=404, detail=f"Keine Werte für {zaehlpunkt}")
    return {"zaehlpunkt": zaehlpunkt, "bezug_kwh_morgen": float(wert), "basis_tage": len(werte)}
