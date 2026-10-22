from fastapi.testclient import TestClient

from viertelwatt.api import app

client = TestClient(app)


def test_health_braucht_keine_datenbank():
    antwort = client.get("/health")
    assert antwort.status_code == 200
    assert antwort.json() == {"status": "ok"}


def test_version_nennt_den_host():
    antwort = client.get("/version")
    assert antwort.status_code == 200
    assert "host" in antwort.json()


def test_ohne_datenbank_antwortet_ready_mit_503(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_SECRET_ID", raising=False)
    assert client.get("/ready").status_code == 503
