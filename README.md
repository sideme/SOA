## Microservices Final Project – Part 1

This repository contains the deliverables for **Part 1: Microservices Design and Dockerization**. The solution demonstrates a modular architecture built around two lightweight Python FastAPI microservices that communicate over HTTP and are containerized with Docker.

- `user-service`: Manages user profiles with CRUD-style endpoints.
- `order-service`: Manages customer orders and validates them against the user service.

Docker Compose orchestrates both services for local development and testing.

### Repository Layout

- `services/user-service`: FastAPI application for user management, SQLite-backed repository, unit tests, Dockerfile, and requirements.
- `services/order-service`: FastAPI application for order management, SQLite-backed repository, unit & integration tests, Dockerfile, and requirements.
- `docs/architecture.md`: Detailed architecture overview, API design, and interaction diagrams.
- `docker-compose.yml`: Multi-container configuration to run both services locally.

### Data Storage & Service Discovery

- Each microservice owns its own SQLite database file (`user_service.db`, `order_service.db`) stored under `/home/appuser/app/data` inside the container. Separate Docker volumes (`user_data`, `order_data`) keep the data isolated and durable across restarts.
- Services communicate over HTTP using semantic REST endpoints. Docker Compose networking provides DNS-style discovery so `order-service` can reach `user-service` via the service name (`http://user-service:8000`).

### Running Locally

```bash
docker compose up --build
```

The command builds both images and starts the API gateway network:

- `user-service` → http://localhost:8000
- `order-service` → http://localhost:8001

To rebuild from scratch:

```bash
docker compose down --volumes
docker compose up --build
```

### Testing

Install dependencies and execute the automated test suites:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r services/user-service/requirements.txt
pip install -r services/order-service/requirements.txt
pytest services/user-service/tests
pytest services/order-service/tests
```

The order-service test suite includes an integration test that boots the user-service application in-process and verifies cross-service communication via HTTP requests, complementing the unit coverage.

### Next Phases

Part 2 onward will build on this foundation by introducing Kubernetes manifests, CI/CD automation, and enhanced observability. Refer to `docs/architecture.md` for planned extensions and design rationale.

