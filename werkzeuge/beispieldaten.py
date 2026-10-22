"""Erzeugt Beispieldaten im Format des Netzbetreibers.

Aufruf:  python werkzeuge/beispieldaten.py --von 2026-10-01 --tage 7 --ziel daten

Die Werte sind erfunden, aber plausibel: Haushalte mit Spitzen am Morgen und
am Abend, eine Bäckerei mit Spitze in der Nacht, Photovoltaik mit Mittagsspitze
und wechselndem Wetter. Gleicher Startwert, gleiche Dateien.

Vereinfachung: Jeder Tag hat 96 Viertelstunden in Ortszeit ohne Zeitzone. Die Tage der
Zeitumstellung (92 oder 100 Viertelstunden) bildet der Generator nicht ab.
"""

import argparse
import math
import random
from datetime import date, datetime, timedelta
from pathlib import Path

HAUSHALTE = [f"HOF-V-{i:03d}" for i in range(1, 63)]
KINDERGARTEN = "HOF-V-063"
BAECKEREI = "HOF-V-064"
ANLAGEN = {"HOF-E-01": 30.0, "HOF-E-02": 30.0, "HOF-E-03": 45.0, "HOF-E-04": 25.0}  # kWp


def haushalt(stunde: float, grundlast: float) -> float:
    morgen = 0.15 * math.exp(-((stunde - 7.0) ** 2) / 1.5)
    abend = 0.25 * math.exp(-((stunde - 19.0) ** 2) / 3.0)
    return grundlast + morgen + abend


def kindergarten(stunde: float, wochenende: bool) -> float:
    if wochenende or not 7 <= stunde < 17:
        return 0.08
    return 0.9


def baeckerei(stunde: float) -> float:
    return 4.5 if 1 <= stunde < 7 else 0.6


# Je Monat: erste und letzte Stunde mit Erzeugung, Breite der Glockenkurve, Anteil der
# Nennleistung zu Mittag. Grobe Werte für Wien, Spitze kurz nach Mittag (Sommerzeit).
SAISON = {
    1: (8, 16, 3.5, 0.35), 2: (7, 17, 4.5, 0.45), 3: (7, 18, 6.0, 0.55),
    4: (6, 20, 9.0, 0.65), 5: (5, 21, 12.0, 0.70), 6: (5, 21, 14.0, 0.75),
    7: (5, 21, 14.0, 0.75), 8: (6, 20, 11.0, 0.70), 9: (7, 19, 8.0, 0.62),
    10: (7, 18, 6.0, 0.55), 11: (8, 16, 4.0, 0.40), 12: (8, 16, 3.0, 0.30),
}


def photovoltaik(stunde: float, kwp: float, wetter: float, monat: int = 10) -> float:
    beginn, ende, breite, anteil = SAISON[monat]
    if not beginn <= stunde <= ende:
        return 0.0
    form = math.exp(-((stunde - 12.75) ** 2) / breite)
    return kwp * anteil * form * wetter * 0.25  # kW mal eine Viertelstunde


def kwh(wert: float) -> str:
    return f"{max(wert, 0):.3f}".replace(".", ",")


def tag_schreiben(tag: date, ziel: Path, rng: random.Random, punkt: bool = False) -> Path:
    wetter = rng.choice([0.25, 0.5, 0.8, 1.0, 1.0])
    wochenende = tag.weekday() >= 5
    grundlasten = {zp: rng.uniform(0.03, 0.09) for zp in HAUSHALTE}
    zeilen = ["zaehlpunkt;zeitpunkt;richtung;kwh"]
    beginn = datetime(tag.year, tag.month, tag.day)
    for i in range(96):
        zeit = beginn + timedelta(minutes=15 * i)
        stunde = zeit.hour + zeit.minute / 60
        stempel = zeit.strftime("%Y-%m-%d %H:%M")
        for zp in HAUSHALTE:
            wert = haushalt(stunde, grundlasten[zp]) * rng.uniform(0.7, 1.3)
            zeilen.append(f"{zp};{stempel};BEZUG;{kwh(wert)}")
        zeilen.append(f"{KINDERGARTEN};{stempel};BEZUG;{kwh(kindergarten(stunde, wochenende) * rng.uniform(0.8, 1.2))}")
        zeilen.append(f"{BAECKEREI};{stempel};BEZUG;{kwh(baeckerei(stunde) * rng.uniform(0.85, 1.15))}")
        for zp, kwp in ANLAGEN.items():
            wert = photovoltaik(stunde, kwp, wetter, tag.month) * rng.uniform(0.9, 1.1)
            zeilen.append(f"{zp};{stempel};EINSPEISUNG;{kwh(wert)}")
    if punkt:
        zeilen = [zeilen[0]] + [z.replace(",", ".") for z in zeilen[1:]]
    datei = ziel / f"messwerte_{tag.isoformat()}.csv"
    datei.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return datei


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--von", type=date.fromisoformat, default=date(2026, 10, 1))
    p.add_argument("--tage", type=int, default=7)
    p.add_argument("--ziel", type=Path, default=Path("daten"))
    p.add_argument("--startwert", type=int, default=2026)
    p.add_argument("--dezimalpunkt", action="store_true",
                   help="Punkt statt Komma, erzeugt eine fehlerhafte Lieferung wie in Vorfall 6")
    a = p.parse_args()
    a.ziel.mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.startwert)
    for n in range(a.tage):
        print(tag_schreiben(a.von + timedelta(days=n), a.ziel, rng, a.dezimalpunkt))


if __name__ == "__main__":
    main()
