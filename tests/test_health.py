from fastapi.testclient import TestClient

from app import __version__
from app.main import app

client = TestClient(app)


def test_health_reports_ok():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "app": "day-ahead-wind-desk", "version": __version__}


def test_openapi_is_served_under_api():
    res = client.get("/api/openapi.json")
    assert res.status_code == 200
    assert "/api/health" in res.json()["paths"]
