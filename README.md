## Microservices Platform Overview

This repository hosts a reference implementation of a two-service Python FastAPI system that can be run with Docker Compose or deployed to Kubernetes. It focuses on clean separation of concerns, automated testing, and production-ready tooling such as CI/CD pipelines and observability integrations.

- `user-service`: Manages user profiles with CRUD-style endpoints.
- `order-service`: Manages customer orders and validates them against the user service.

Docker Compose orchestrates both services for local development and testing.

### Repository Layout

- `services/user-service`: FastAPI application for user management, SQLite-backed repository, unit tests, Dockerfile, and requirements.
- `services/order-service`: FastAPI application for order management, SQLite-backed repository, unit & integration tests, Dockerfile, and requirements.
- `k8s/`: Kubernetes manifests for deploying services (Deployments, Services, ConfigMaps, PVCs, Ingress).
- `.github/workflows/`: CI/CD pipeline configurations (GitHub Actions).
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

## Part 2: Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (local with minikube/kind, or cloud-based)
- `kubectl` configured to access your cluster
- `kustomize` (optional, for applying all manifests at once)

### Deployment

Deploy all services using Kustomize:

```bash
kubectl apply -k k8s/
```

Or deploy individually:

```bash
# User Service
kubectl apply -f k8s/user-service/

# Order Service
kubectl apply -f k8s/order-service/

# Ingress (requires ingress controller)
kubectl apply -f k8s/ingress.yaml
```

### Verify Deployment

```bash
# Check pods
kubectl get pods

# Check services
kubectl get services

# Check deployments
kubectl get deployments

# View logs
kubectl logs -f deployment/user-service
kubectl logs -f deployment/order-service
```

### Access Services

- **Port Forward** (for local access):
  ```bash
  kubectl port-forward service/user-service 8000:8000
  kubectl port-forward service/order-service 8001:8000
  ```

- **Ingress** (if configured):
  - User Service: `http://localhost/users`
  - Order Service: `http://localhost/orders`

### Kubernetes Features

- **High Availability**: 2 replicas per service for redundancy
- **Health Checks**: Liveness and readiness probes configured
- **Resource Limits**: CPU and memory limits set for each pod
- **Persistent Storage**: PVCs for data persistence
- **Service Discovery**: ClusterIP services for internal communication
- **Configuration Management**: ConfigMaps for environment variables

## Part 3: CI/CD and Observability

### CI/CD Pipeline

The project includes GitHub Actions workflows for automated testing, building, and deployment:

1. **Test Workflow** (`.github/workflows/ci-cd.yml`):
   - Runs unit tests for both services
   - Builds and pushes Docker images to GitHub Container Registry
   - Deploys to Kubernetes on main branch pushes

2. **Integration Test Workflow** (`.github/workflows/docker-compose-test.yml`):
   - Tests services in Docker Compose environment
   - Verifies end-to-end functionality
   - Validates metrics endpoints

### Observability Features

Both services include comprehensive observability:

#### Metrics (Prometheus)

- **HTTP Metrics**: Request counts and durations by endpoint
- **External Service Calls**: Track calls to user-service from order-service
- **Metrics Endpoint**: `/metrics` on both services

Access metrics:
```bash
curl http://localhost:8000/metrics
curl http://localhost:8001/metrics
```

#### Logging

- Structured logging with timestamps and log levels
- Request/response logging with duration tracking
- Error logging for failed operations
- External service call logging

#### Health Checks

- `/health` endpoint for Kubernetes probes
- Liveness probe: checks if service is running
- Readiness probe: checks if service is ready to accept traffic

### Monitoring Setup

To set up Prometheus monitoring:

1. Install Prometheus Operator or standalone Prometheus
2. Configure ServiceMonitor or scrape configs to collect metrics from:
   - `user-service:8000/metrics`
   - `order-service:8000/metrics`
3. Set up Grafana dashboards for visualization

### CI/CD Setup

1. **GitHub Secrets** (required for deployment):
   - `KUBECONFIG`: Base64-encoded kubeconfig file for your cluster

2. **Container Registry**:
   - Images are pushed to GitHub Container Registry
   - Format: `ghcr.io/<owner>/<service-name>:<tag>`

3. **Automatic Deployment**:
   - Pushes to `main` branch trigger deployment
   - Pull requests trigger tests only

