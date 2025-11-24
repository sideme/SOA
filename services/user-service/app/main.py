import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
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

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "user_service.db"
DATABASE_PATH = Path(os.getenv("USER_DB_PATH", DEFAULT_DB_PATH))


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None


class User(BaseModel):
    id: UUID
    name: str
    email: EmailStr


class SQLiteUserRepository:
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
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE
                )
                """
            )

    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> User:
        return User(id=UUID(row["id"]), name=row["name"], email=row["email"])

    def list_users(self) -> List[User]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id, name, email FROM users ORDER BY name").fetchall()
        return [self._row_to_user(row) for row in rows]

    def get_user(self, user_id: UUID) -> User:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name, email FROM users WHERE id = ?",
                (str(user_id),),
            ).fetchone()
        if row is None:
            raise KeyError("User not found")
        return self._row_to_user(row)

    def create_user(self, data: UserCreate) -> User:
        user = User(id=uuid4(), name=data.name, email=data.email)
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
                    (str(user.id), user.name, user.email),
                )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed: users.email" in str(exc):
                raise ValueError("Email already registered") from exc
            raise
        return user

    def update_user(self, user_id: UUID, data: UserUpdate) -> User:
        existing = self.get_user(user_id)
        updates = data.model_dump(exclude_unset=True)
        if not updates:
            return existing

        fields = ", ".join(f"{column} = ?" for column in updates.keys())
        values = list(updates.values())
        try:
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE users SET {fields} WHERE id = ?",
                    (*values, str(user_id)),
                )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed: users.email" in str(exc):
                raise ValueError("Email already registered") from exc
            raise
        return self.get_user(user_id)

    def delete_user(self, user_id: UUID) -> None:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM users WHERE id = ?",
                (str(user_id),),
            )
        if cursor.rowcount == 0:
            raise KeyError("User not found")

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM users")


repository = SQLiteUserRepository(DATABASE_PATH)


def get_repository() -> SQLiteUserRepository:
    return repository


app = FastAPI(
    title="User Service",
    version="0.1.0",
    description="Manage user profiles for the microservices final project.",
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
    "/users",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
    tags=["users"],
)
def create_user(
    payload: UserCreate,
    repo: SQLiteUserRepository = Depends(get_repository),
) -> User:
    try:
        logger.info(f"Creating user with email: {payload.email}")
        user = repo.create_user(payload)
        logger.info(f"User created successfully: {user.id}")
        return user
    except ValueError as exc:
        logger.warning(f"Failed to create user: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@app.get("/users", response_model=List[User], tags=["users"])
def list_users(repo: SQLiteUserRepository = Depends(get_repository)) -> List[User]:
    return repo.list_users()


@app.get("/users/{user_id}", response_model=User, tags=["users"])
def get_user(
    user_id: UUID,
    repo: SQLiteUserRepository = Depends(get_repository),
) -> User:
    try:
        return repo.get_user(user_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc


@app.put("/users/{user_id}", response_model=User, tags=["users"])
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    repo: SQLiteUserRepository = Depends(get_repository),
) -> User:
    try:
        return repo.update_user(user_id, payload)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@app.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["users"],
)
def delete_user(
    user_id: UUID,
    repo: SQLiteUserRepository = Depends(get_repository),
) -> None:
    try:
        repo.delete_user(user_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc

