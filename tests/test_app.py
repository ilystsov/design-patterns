from fastapi.testclient import TestClient

from server.asgi import app

client = TestClient(app)


def test_find_parents() -> None:
    response = client.get("/api/parents")
    assert response.status_code == 200
    assert response.json() == {"message": "found parents"}


def test_report_weather() -> None:
    response = client.get("/api/weather")
    assert response.status_code == 200
    assert response.json() == {"message": "weather report"}
