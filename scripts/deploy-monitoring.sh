#!/bin/bash

set -e

echo "🚀 Deploying Monitoring Stack (Prometheus, Grafana, Loki, Promtail)"

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl not found. Please install kubectl first.${NC}"
    exit 1
fi

# Check if Kubernetes cluster is accessible
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ Cannot connect to Kubernetes cluster${NC}"
    exit 1
fi

echo -e "${YELLOW}📦 Step 1: Deploying monitoring components...${NC}"
kubectl apply -f k8s/monitoring/

echo -e "${YELLOW}⏳ Step 2: Waiting for pods to be ready...${NC}"

# Wait for Prometheus
echo "Waiting for Prometheus..."
kubectl wait --for=condition=ready pod -l app=prometheus --timeout=5m || {
    echo -e "${RED}❌ Prometheus failed to start${NC}"
    exit 1
}

# Wait for Grafana
echo "Waiting for Grafana..."
kubectl wait --for=condition=ready pod -l app=grafana --timeout=5m || {
    echo -e "${RED}❌ Grafana failed to start${NC}"
    exit 1
}

# Wait for Loki
echo "Waiting for Loki..."
kubectl wait --for=condition=ready pod -l app=loki --timeout=5m || {
    echo -e "${RED}❌ Loki failed to start${NC}"
    exit 1
}

# Wait for Promtail
echo "Waiting for Promtail..."
kubectl wait --for=condition=ready pod -l app=promtail --timeout=5m || {
    echo -e "${YELLOW}⚠️  Promtail may take longer to start (DaemonSet)${NC}"
}

echo -e "${GREEN}✅ All monitoring components deployed successfully!${NC}"

echo ""
echo -e "${YELLOW}📊 Step 3: Verifying deployment...${NC}"
kubectl get pods | grep -E "prometheus|grafana|loki|promtail"

echo ""
echo -e "${GREEN}🎉 Monitoring stack is ready!${NC}"
echo ""
echo "To access the monitoring tools:"
echo ""
echo "📈 Prometheus:"
echo "   kubectl port-forward service/prometheus 9090:9090"
echo "   Then open http://localhost:9090"
echo ""
echo "📊 Grafana:"
echo "   kubectl port-forward service/grafana 3000:3000"
echo "   Then open http://localhost:3000"
echo "   Default credentials: admin / admin"
echo ""
echo "📝 Loki:"
echo "   kubectl port-forward service/loki 3100:3100"
echo "   (Usually accessed through Grafana)"
echo ""
echo "For detailed usage instructions, see: docs/Part3_Monitoring_Setup.md"

