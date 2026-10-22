from datetime import date
from decimal import Decimal

import pytest

from viertelwatt.kern import (
    FormatFehler,
    deckungsgrad,
    lies_csv,
    prognose,
    tageswerte,
    zahl,
)

KOPF = "zaehlpunkt;zeitpunkt;richtung;kwh\n"


def test_komma_ist_das_dezimalzeichen():
    assert zahl("0,084") == Decimal("0.084")


def test_dezimalpunkt_wird_abgelehnt():
    # Vorfall 6: aus 0.214 wurde 214. Das darf nie wieder still passieren.
    with pytest.raises(FormatFehler):
        zahl("0.214")


def test_datei_mit_dezimalpunkt_wird_ganz_abgelehnt():
    text = KOPF + "HOF-V-001;2026-06-14 00:00;BEZUG;0.214\n"
    with pytest.raises(FormatFehler):
        lies_csv(text)


@pytest.mark.parametrize("text", ["NaN", "Infinity", "1e3", "0,08x"])
def test_keine_zahl_wird_abgelehnt(text):
    with pytest.raises(FormatFehler):
        zahl(text)


def test_datei_aus_excel_mit_bom_wird_gelesen():
    text = "\ufeff" + KOPF + "HOF-V-001;2026-10-01 00:00;BEZUG;0,051\n"
    assert len(lies_csv(text).messwerte) == 1


def test_falsche_kopfzeile_wird_abgelehnt():
    with pytest.raises(FormatFehler):
        lies_csv("zp,zeit,richtung,kwh\nHOF-V-001,2026-10-01 00:00,BEZUG,0\n")


def test_gueltige_zeilen_werden_gelesen():
    text = KOPF + (
        "HOF-V-001;2026-10-01 00:00;BEZUG;0,084\n"
        "HOF-E-03;2026-10-02 13:00;EINSPEISUNG;6,583\n"
    )
    ergebnis = lies_csv(text)
    assert len(ergebnis.messwerte) == 2
    assert ergebnis.verworfen == []


@pytest.mark.parametrize(
    "zeile, grund",
    [
        ("HOF-V-001;2026-10-01 00:00;BEZUG;-0,1", "unplausibler"),
        ("HOF-V-001;2026-10-01 00:00;BEZUG;99,0", "unplausibler"),
        ("HOF-V-001;2026-10-01 00:00;STROM;0,1", "Richtung"),
        ("HOF-V-001;01.10.2026 00:00;BEZUG;0,1", "Zeitpunkt"),
        ("HOF-V-001;2026-10-01 00:00;BEZUG;", "fehlt"),
        ("HOF-V-001;2026-10-01 00:00;BEZUG", "Spalten"),
    ],
)
def test_kaputte_zeilen_werden_verworfen(zeile, grund):
    ergebnis = lies_csv(KOPF + zeile + "\n")
    assert ergebnis.messwerte == []
    assert grund in ergebnis.verworfen[0]


def test_doppelte_zeile_zaehlt_nur_einmal():
    zeile = "HOF-V-001;2026-10-01 00:00;BEZUG;0,100\n"
    ergebnis = lies_csv(KOPF + zeile + zeile)
    assert len(ergebnis.messwerte) == 1
    assert "doppelt" in ergebnis.verworfen[0]


def test_tageswerte_summieren_je_zaehlpunkt_und_tag():
    text = KOPF + (
        "HOF-V-001;2026-10-01 00:00;BEZUG;0,100\n"
        "HOF-V-001;2026-10-01 00:15;BEZUG;0,200\n"
        "HOF-V-001;2026-10-02 00:00;BEZUG;0,500\n"
        "HOF-E-01;2026-10-01 12:00;EINSPEISUNG;7,000\n"
    )
    werte = tageswerte(lies_csv(text).messwerte)
    nach_schluessel = {(w.zaehlpunkt, w.datum): w for w in werte}
    assert nach_schluessel[("HOF-V-001", date(2026, 10, 1))].bezug_kwh == Decimal("0.300")
    assert nach_schluessel[("HOF-V-001", date(2026, 10, 2))].bezug_kwh == Decimal("0.500")
    assert nach_schluessel[("HOF-E-01", date(2026, 10, 1))].einspeisung_kwh == Decimal("7.000")


def test_deckungsgrad_in_prozent():
    assert deckungsgrad(Decimal("200"), Decimal("50")) == Decimal("25.0")


def test_deckungsgrad_ohne_verbrauch_ist_leer():
    assert deckungsgrad(Decimal("0"), Decimal("10")) is None


def test_prognose_ist_mittelwert_der_letzten_sieben_tage():
    werte = [Decimal(x) for x in ("100", "1", "2", "3", "4", "5", "6", "7")]
    assert prognose(werte) == Decimal("4.000")


def test_prognose_ohne_daten_ist_leer():
    assert prognose([]) is None
