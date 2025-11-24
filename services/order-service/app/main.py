import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID, uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

external_service_calls = Counter(
    'external_service_calls_total',
    'Total external service calls',
    ['service', 'status']
)

external_service_duration = Histogram(
    'external_service_duration_seconds',
    'External service call duration in seconds',
    ['service']
)

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "order_service.db"
DATABASE_PATH = Path(os.getenv("ORDER_DB_PATH", DEFAULT_DB_PATH))


class OrderItem(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50)
    quantity: int = Field(..., ge=1, le=1000)
    unit_price: float = Field(..., gt=0)


class OrderCreate(BaseModel):
    user_id: UUID
    items: List[OrderItem] = Field(..., min_length=1)


class Order(BaseModel):
    id: UUID
    user_id: UUID
    items: List[OrderItem]
    total_amount: float


class SQLiteOrderRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    items TEXT NOT NULL,
                    total_amount REAL NOT NULL
                )
                """
            )

    @staticmethod
    def _row_to_order(row: sqlite3.Row) -> Order:
        raw_items = json.loads(row["items"])
        items = [OrderItem(**item) for item in raw_items]
        return Order(
            id=UUID(row["id"]),
            user_id=UUID(row["user_id"]),
            items=items,
            total_amount=row["total_amount"],
        )

    def list_orders(self) -> List[Order]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, user_id, items, total_amount FROM orders ORDER BY rowid"
            ).fetchall()
        return [self._row_to_order(row) for row in rows]

    def get_order(self, order_id: UUID) -> Order:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, user_id, items, total_amount FROM orders WHERE id = ?",
                (str(order_id),),
            ).fetchone()
        if row is None:
            raise KeyError("Order not found")
        return self._row_to_order(row)

    def create_order(self, data: OrderCreate) -> Order:
        total = round(sum(item.quantity * item.unit_price for item in data.items), 2)
        order = Order(
            id=uuid4(),
            user_id=data.user_id,
            items=data.items,
            total_amount=total,
        )
        serialized_items = json.dumps([item.model_dump() for item in order.items])
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO orders (id, user_id, items, total_amount) VALUES (?, ?, ?, ?)",
                (str(order.id), str(order.user_id), serialized_items, order.total_amount),
            )
        return order

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM orders")


class UserServiceClient:
    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = base_url or os.getenv("USER_SERVICE_URL", "http://localhost:8000")

    def ensure_user_exists(self, user_id: UUID) -> None:
        url = f"{self.base_url}/users/{user_id}"
        start_time = time.time()
        try:
            logger.info(f"Validating user with user-service: {user_id}")
            response = httpx.get(url, timeout=5.0)
            duration = time.time() - start_time
            
            external_service_duration.labels(service="user-service").observe(duration)
            external_service_calls.labels(service="user-service", status=response.status_code).inc()
            
            if response.status_code == status.HTTP_404_NOT_FOUND:
                logger.warning(f"User not found: {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User does not exist",
                )

            if not response.is_success:
                logger.error(f"User service returned error: {response.status_code}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to validate user",
                )
            
            logger.info(f"User validated successfully: {user_id}")
        except httpx.RequestError as exc:
            duration = time.time() - start_time
            external_service_duration.labels(service="user-service").observe(duration)
            external_service_calls.labels(service="user-service", status="error").inc()
            logger.error(f"User service unavailable: {str(exc)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="User service unavailable",
            ) from exc


def get_user_service_client() -> UserServiceClient:
    return UserServiceClient()


repository = SQLiteOrderRepository(DATABASE_PATH)


def get_repository() -> SQLiteOrderRepository:
    return repository


def reset_orders_repository() -> None:
    repository.clear()


app = FastAPI(
    title="Order Service",
    version="0.1.0",
    description="Create and retrieve orders while validating users via the user service.",
)

# Middleware for metrics and logging
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    method = request.method
    path = request.url.path
    
    logger.info(f"Request: {method} {path}")
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    status_code = response.status_code
    
    # Record metrics
    http_requests_total.labels(method=method, endpoint=path, status=status_code).inc()
    http_request_duration_seconds.labels(method=method, endpoint=path).observe(duration)
    
    logger.info(f"Response: {method} {path} - {status_code} - {duration:.3f}s")
    
    return response


@app.get("/health", tags=["health"])
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics", tags=["metrics"])
def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post(
    "/orders",
    response_model=Order,
    status_code=status.HTTP_201_CREATED,
    tags=["orders"],
)
def create_order(
    payload: OrderCreate,
    user_client: UserServiceClient = Depends(get_user_service_client),
    repo: SQLiteOrderRepository = Depends(get_repository),
) -> Order:
    logger.info(f"Creating order for user: {payload.user_id} with {len(payload.items)} items")
    user_client.ensure_user_exists(payload.user_id)
    order = repo.create_order(payload)
    logger.info(f"Order created successfully: {order.id} - Total: ${order.total_amount}")
    return order


@app.get("/orders", response_model=List[Order], tags=["orders"])
def list_orders(repo: SQLiteOrderRepository = Depends(get_repository)) -> List[Order]:
    return repo.list_orders()


@app.get("/orders/{order_id}", response_model=Order, tags=["orders"])
def get_order(
    order_id: UUID,
    repo: SQLiteOrderRepository = Depends(get_repository),
) -> Order:
    try:
        return repo.get_order(order_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        ) from exc

