"""Fachlogik ohne Datenbank und Netz.

Alles hier ist eine reine Funktion: gleiche Eingabe, gleiches Ergebnis.
Deshalb setzen die Tests genau hier an.
"""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

KOPFZEILE = ["zaehlpunkt", "zeitpunkt", "richtung", "kwh"]
RICHTUNGEN = {"BEZUG", "EINSPEISUNG"}

# Mehr als 50 kWh in einer Viertelstunde entspricht einer Dauerleistung von 200 kW.
# Das schafft in dieser Gemeinschaft kein Anschluss. Solche Werte sind Messfehler.
HOECHSTWERT_KWH = Decimal("50")

DREI_STELLEN = Decimal("0.001")

# Ziffern, optional ein Komma mit Nachkommastellen, optional ein Minus davor.
# "NaN", "Infinity" oder "1e3" sind für Python gültige Zahlen, für uns nicht.
ZAHLFORMAT = re.compile(r"-?\d+(,\d+)?")


class FormatFehler(ValueError):
    """Die Datei als Ganzes ist unbrauchbar und wird nicht verarbeitet."""


@dataclass(frozen=True)
class Messwert:
    zaehlpunkt: str
    zeitpunkt: datetime  # Beginn der Viertelstunde
    richtung: str
    kwh: Decimal


@dataclass(frozen=True)
class Tageswert:
    zaehlpunkt: str
    datum: date
    bezug_kwh: Decimal
    einspeisung_kwh: Decimal


@dataclass(frozen=True)
class Ergebnis:
    messwerte: list[Messwert]
    verworfen: list[str]  # je verworfener Zeile ein lesbarer Grund


def zahl(text: str) -> Decimal:
    """Liest eine Zahl mit Dezimalkomma, zum Beispiel '0,084'.

    Ein Dezimalpunkt ist kein Tippfehler, sondern ein anderes Format.
    Er wird abgelehnt, statt still falsch gelesen zu werden (Vorfall 6).
    """
    t = text.strip()
    if "." in t:
        raise FormatFehler(f"Dezimalpunkt statt Komma: {text!r}")
    if not ZAHLFORMAT.fullmatch(t):
        raise FormatFehler(f"keine Zahl: {text!r}")
    return Decimal(t.replace(",", "."))


def lies_csv(text: str) -> Ergebnis:
    """Liest eine Datei des Netzbetreibers und trennt brauchbare von verworfenen Zeilen.

    FormatFehler bei falscher Kopfzeile oder falschem Zahlenformat: dann ist die
    ganze Datei verdächtig. Einzelne kaputte Zeilen werden verworfen und gezählt.
    """
    # Exporte aus Excel beginnen oft mit einer unsichtbaren Byte-Order-Mark.
    leser = csv.reader(io.StringIO(text.removeprefix("\ufeff")), delimiter=";")
    kopf = next(leser, None)
    if kopf is None or [k.strip().lower() for k in kopf] != KOPFZEILE:
        raise FormatFehler(f"Kopfzeile erwartet {';'.join(KOPFZEILE)}, gefunden {kopf}")

    messwerte: list[Messwert] = []
    verworfen: list[str] = []
    gesehen: set[tuple[str, datetime, str]] = set()

    for nr, zeile in enumerate(leser, start=2):
        if not zeile or all(not feld.strip() for feld in zeile):
            continue
        if len(zeile) != 4:
            verworfen.append(f"Zeile {nr}: {len(zeile)} statt 4 Spalten")
            continue
        zp, zeit, richtung, menge = (feld.strip() for feld in zeile)
        try:
            zeitpunkt = datetime.strptime(zeit, "%Y-%m-%d %H:%M")
        except ValueError:
            verworfen.append(f"Zeile {nr}: Zeitpunkt {zeit!r} unlesbar")
            continue
        if richtung not in RICHTUNGEN:
            verworfen.append(f"Zeile {nr}: unbekannte Richtung {richtung!r}")
            continue
        if menge == "":
            verworfen.append(f"Zeile {nr}: Messwert fehlt")
            continue
        kwh = zahl(menge)
        if kwh < 0 or kwh > HOECHSTWERT_KWH:
            verworfen.append(f"Zeile {nr}: unplausibler Wert {menge}")
            continue
        schluessel = (zp, zeitpunkt, richtung)
        if schluessel in gesehen:
            verworfen.append(f"Zeile {nr}: doppelt")
            continue
        gesehen.add(schluessel)
        messwerte.append(Messwert(zp, zeitpunkt, richtung, kwh))

    return Ergebnis(messwerte, verworfen)


def tageswerte(messwerte: list[Messwert]) -> list[Tageswert]:
    """Summiert Viertelstundenwerte je Zählpunkt und Tag."""
    summen: dict[tuple[str, date], dict[str, Decimal]] = defaultdict(
        lambda: {"BEZUG": Decimal(0), "EINSPEISUNG": Decimal(0)}
    )
    for m in messwerte:
        summen[(m.zaehlpunkt, m.zeitpunkt.date())][m.richtung] += m.kwh
    return [
        Tageswert(zp, tag, s["BEZUG"], s["EINSPEISUNG"])
        for (zp, tag), s in sorted(summen.items())
    ]


def deckungsgrad(verbrauch_kwh: Decimal, erzeugung_kwh: Decimal) -> Decimal | None:
    """Anteil des Verbrauchs, den die eigenen Anlagen rechnerisch decken, in Prozent.

    Über 100 Prozent heißt: an diesem Tag wurde mehr erzeugt als verbraucht.
    """
    if verbrauch_kwh == 0:
        return None
    return (erzeugung_kwh / verbrauch_kwh * 100).quantize(Decimal("0.1"))


def prognose(letzte_werte: list[Decimal], tage: int = 7) -> Decimal | None:
    """Einfache Prognose für morgen: Mittelwert der letzten Tage.

    Bewusst schlicht. Es geht in diesem Kurs um den Betrieb, nicht um das Modell.
    """
    werte = letzte_werte[-tage:]
    if not werte:
        return None
    return (sum(werte) / len(werte)).quantize(DREI_STELLEN)
