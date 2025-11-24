# Project Architecture Overview

This document summarizes the current architecture of the microservices platform so the
README can reference a clean, English-only description. It replaces earlier
working notes that were removed before publishing the repository.

---

## 1. System Components

| Layer            | Components                                                                 | Purpose                                                |
|------------------|-----------------------------------------------------------------------------|--------------------------------------------------------|
| Client / Tools   | `curl`, Postman, automated tests                                            | Exercise APIs and produce monitoring data              |
| Gateway / Ingress| Docker Desktop Kubernetes port-forward (local cluster only)                | Provides controlled local-only access to services      |
| Application Tier | `user-service`, `order-service` (FastAPI + Python)                         | Implements business logic                              |
| Data / Storage   | PersistentVolumeClaims (per service) + SQLite files mounted via PVCs       | Ensures state survives pod restarts                    |
| Observability    | Prometheus, Grafana, Loki, Promtail                                        | Metrics collection, dashboards, log aggregation        |
| Automation       | GitHub Actions (`ci-cd.yml`), helper scripts in `scripts/`                 | CI/CD, deployment, validation                          |

---

## 2. Microservice Responsibilities

- **user-service**
  - Manages user CRUD operations.
  - Exposes `/health` and `/metrics`.
  - Emits structured logs consumed by Promtail.

- **order-service**
  - Depends on user-service for validation.
  - Tracks order lifecycle and external-service call counts.
  - Exposes the same health/metrics endpoints for consistency.

---

## 3. Kubernetes Resources

Each service is provisioned via manifests under `k8s/`:

- `Deployment`: controls replica count, rolling updates, and probes.
- `Service (ClusterIP)`: provides stable DNS for intra-cluster access.
- `ConfigMap`: injects environment variables (DB paths, service URLs, etc.).
- `PersistentVolumeClaim`: stores SQLite databases and durable artifacts.
- `HorizontalPodAutoscaler`: scales pods based on CPU/memory.

Monitoring manifests (Prometheus, Grafana, Loki, Promtail) live in
`k8s/monitoring/` and are applied together with `kubectl apply -k k8s/`.

---

## 4. CI/CD and Automation Flow

```mermaid
flowchart LR
    A[Git Push] --> B[GitHub Actions]
    B --> C[Run Unit + Integration Tests]
    B --> D[Build & Push Docker Images]
    D --> E[Deploy to Kubernetes (kubectl)]
    E --> F[Smoke Tests / Validation Scripts]
```

Supporting scripts:

- `scripts/deploy-local.sh`: full application stack deployment.
- `scripts/deploy-monitoring.sh`: Prometheus/Grafana/Loki/Promtail stack.
- `scripts/verify-networking-scaling-discovery.sh`: validation checks.

---

## 5. Observability Stack

1. **Prometheus**
   - Scrapes `/metrics` from both services.
   - Feeds Grafana dashboards.

2. **Grafana**
   - Pre-provisioned data sources (Prometheus + Loki).
   - Dashboards visualize request throughput, latency, error budgets, and
     external-service calls.

3. **Loki + Promtail**
   - Promtail DaemonSet forwards pod logs to Loki.
   - Grafana Explore provides query access even when logs are sparse in the
     local Docker Desktop environment.

---

## 6. Deployment Workflow (Local Cluster)

1. Enable Kubernetes in Docker Desktop and confirm connectivity via
   `kubectl cluster-info`.
2. Build images locally (`docker build`) or let CI/CD handle it.
3. Apply manifests with `kubectl apply -k k8s/`.
4. Run smoke tests or curl commands against the forwarded ports.
5. Optionally deploy monitoring stack and view dashboards/logs via
   port-forwarding.

---

## 7. Security / Access Notes

- Local-only deployment: no ingress controller; port-forwarding is required.
- Secrets are handled via environment variables (no secrets store required for
  the final submission).
- RBAC for Promtail is provisioned via manifests to permit pod log discovery.

---

## 8. Future Improvements

- Introduce a real ingress and TLS termination when targeting cloud clusters.
- Replace SQLite with managed databases and move PVCs to dynamic provisioners.
- Add Alertmanager rules and automated alert routing.
- Extend CI/CD with end-to-end tests running against a temporary cluster.


