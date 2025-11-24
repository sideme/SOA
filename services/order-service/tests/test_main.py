import importlib.util
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import (
    SQLiteOrderRepository,
    app as order_app,
    get_repository as get_order_repository,
    get_user_service_client,
)

USER_SERVICE_MAIN = Path(__file__).resolve().parents[2] / "user-service" / "app" / "main.py"


def load_user_service(db_path: Path):
    module_name = f"user_service_app_tests_{uuid4().hex}"
    original = os.environ.get("USER_DB_PATH")
    os.environ["USER_DB_PATH"] = str(db_path)
    
    # Clear Prometheus registry to avoid metric conflicts when loading module
    from prometheus_client import REGISTRY
    collectors_to_remove = list(REGISTRY._collector_to_names.keys())
    for collector in collectors_to_remove:
        try:
            REGISTRY.unregister(collector)
        except (KeyError, ValueError):
            pass
    
    spec = importlib.util.spec_from_file_location(module_name, USER_SERVICE_MAIN)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    repo = module.SQLiteUserRepository(db_path)
    module.app.dependency_overrides[module.get_repository] = lambda: repo
    if original is not None:
        os.environ["USER_DB_PATH"] = original
    else:
        os.environ.pop("USER_DB_PATH", None)
    return module, repo


@pytest.fixture
def client(tmp_path) -> TestClient:
    repo = SQLiteOrderRepository(tmp_path / "orders.db")
    order_app.dependency_overrides[get_order_repository] = lambda: repo
    with TestClient(order_app) as test_client:
        yield test_client
    order_app.dependency_overrides.clear()
    repo.clear()


def test_healthcheck(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_order_success(client: TestClient) -> None:
    class StubUserClient:
        def __init__(self) -> None:
            self.called_with: UUID | None = None

        def ensure_user_exists(self, user_id: UUID) -> None:
            self.called_with = user_id

    stub = StubUserClient()
    order_app.dependency_overrides[get_user_service_client] = lambda: stub

    user_id = uuid4()
    payload = {
        "user_id": str(user_id),
        "items": [
            {"sku": "ABC-123", "quantity": 2, "unit_price": 19.99},
            {"sku": "XYZ-789", "quantity": 1, "unit_price": 5.5},
        ],
    }

    response = client.post("/orders", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == payload["user_id"]
    assert body["total_amount"] == pytest.approx(45.48, rel=1e-3)
    assert stub.called_with == user_id


def test_create_order_rejects_missing_user(client: TestClient) -> None:
    class RejectingUserClient:
        def ensure_user_exists(self, user_id: UUID) -> None:
            raise HTTPException(status_code=400, detail="User does not exist")

    order_app.dependency_overrides[get_user_service_client] = lambda: RejectingUserClient()

    user_id = uuid4()
    payload = {
        "user_id": str(user_id),
        "items": [{"sku": "ONLY-1", "quantity": 1, "unit_price": 10.0}],
    }

    response = client.post("/orders", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "User does not exist"


def test_create_order_with_user_service_integration(client: TestClient, tmp_path) -> None:
    user_db_path = tmp_path / "user-service.db"
    user_module, _ = load_user_service(user_db_path)

    try:
        with TestClient(user_module.app) as user_client:
            user_payload = {"name": "Carol Customer", "email": "carol@example.com"}
            create_resp = user_client.post("/users", json=user_payload)
            assert create_resp.status_code == 201
            user_id = create_resp.json()["id"]

            class InProcessUserClient:
                def ensure_user_exists(self, user_id: UUID) -> None:
                    response = user_client.get(f"/users/{user_id}")
                    if response.status_code == 404:
                        raise HTTPException(status_code=400, detail="User does not exist")
                    response.raise_for_status()

            order_app.dependency_overrides[get_user_service_client] = lambda: InProcessUserClient()

            order_payload = {
                "user_id": user_id,
                "items": [
                    {"sku": "BUNDLE-1", "quantity": 3, "unit_price": 4.0},
                    {"sku": "BUNDLE-2", "quantity": 1, "unit_price": 2.5},
                ],
            }

            response = client.post("/orders", json=order_payload)
            assert response.status_code == 201
            body = response.json()
            assert body["user_id"] == user_id
            assert body["total_amount"] == pytest.approx(14.5, rel=1e-3)
    finally:
        order_app.dependency_overrides.pop(get_user_service_client, None)
        user_module.app.dependency_overrides.clear()

