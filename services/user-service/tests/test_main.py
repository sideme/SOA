import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import SQLiteUserRepository, app, get_repository  # noqa: E402


@pytest.fixture
def client(tmp_path) -> TestClient:
    db_path = tmp_path / "users.db"
    repo = SQLiteUserRepository(db_path)
    app.dependency_overrides[get_repository] = lambda: repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_healthcheck(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_fetch_user(client: TestClient) -> None:
    payload = {"name": "Alice Example", "email": "alice@example.com"}
    create_response = client.post("/users", json=payload)
    assert create_response.status_code == 201
    created_user = create_response.json()
    assert created_user["name"] == payload["name"]
    assert created_user["email"] == payload["email"]
    user_id = created_user["id"]

    fetch_response = client.get(f"/users/{user_id}")
    assert fetch_response.status_code == 200
    assert fetch_response.json() == created_user


def test_email_uniqueness(client: TestClient) -> None:
    payload = {"name": "Bob Example", "email": "bob@example.com"}
    first = client.post("/users", json=payload)
    assert first.status_code == 201

    duplicate = client.post("/users", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Email already registered"

