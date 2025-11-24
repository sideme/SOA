# Kubernetes Manifests

This directory contains Kubernetes manifests for deploying the microservices.

## Structure

```
k8s/
├── user-service/
│   ├── configmap.yaml      # Environment configuration
│   ├── deployment.yaml     # Deployment with replicas
│   ├── service.yaml         # ClusterIP service
│   └── pvc.yaml            # Persistent volume claim
├── order-service/
│   ├── configmap.yaml      # Environment configuration
│   ├── deployment.yaml     # Deployment with replicas
│   ├── service.yaml         # ClusterIP service
│   └── pvc.yaml            # Persistent volume claim
├── ingress.yaml            # Ingress for external access
└── kustomization.yaml      # Kustomize configuration
```

## Quick Start

Deploy all services:

```bash
kubectl apply -k k8s/
```

## Individual Components

### ConfigMaps

Store environment variables:
- `user-service-config`: Database path configuration
- `order-service-config`: Database path and user service URL

### Deployments

Manage pod replicas:
- 2 replicas per service for high availability
- Health checks configured (liveness and readiness probes)
- Resource limits set (CPU and memory)

### Services

ClusterIP services for internal communication:
- `user-service`: Port 8000
- `order-service`: Port 8000

### PersistentVolumeClaims

Persistent storage for databases:
- `user-service-pvc`: 1Gi storage
- `order-service-pvc`: 1Gi storage

### Ingress

Optional ingress for external access:
- Requires ingress controller (e.g., nginx-ingress)
- Routes `/users` to user-service
- Routes `/orders` to order-service

## Customization

### Change Replica Count

Edit `deployment.yaml` files:

```yaml
spec:
  replicas: 3  # Change from 2 to 3
```

### Adjust Resource Limits

Edit `deployment.yaml` files:

```yaml
resources:
  requests:
    memory: "256Mi"  # Increase from 128Mi
    cpu: "200m"      # Increase from 100m
  limits:
    memory: "512Mi"  # Increase from 256Mi
    cpu: "1000m"     # Increase from 500m
```

### Update Image Tags

Edit `deployment.yaml` files:

```yaml
containers:
- name: user-service
  image: your-registry/user-service:v1.0.0  # Update tag
```

## See Also

- [Kubernetes Deployment Guide](../docs/kubernetes-deployment.md)
- [CI/CD and Observability Guide](../docs/cicd-observability.md)

