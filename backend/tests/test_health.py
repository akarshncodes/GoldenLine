"""Phase 0 regression: the health check + DB connection still work."""


def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["api"] == "up"
    assert body["database"] == "up"


def test_root_reports_current_phase(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "FR-22" in res.json()["phase"]
