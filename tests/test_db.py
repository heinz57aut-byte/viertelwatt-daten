import pytest

from viertelwatt import db


def test_ohne_angaben_gibt_es_eine_klare_fehlermeldung(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_SECRET_ID", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_SECRET_ID"):
        db.datenbank_url()


def test_direkte_adresse_hat_vorrang_vor_dem_tresor(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://a:b@db:5432/viertelwatt")
    monkeypatch.setenv("DATABASE_SECRET_ID", "viertelwatt/datenbank")
    assert db.datenbank_url() == "postgresql://a:b@db:5432/viertelwatt"
