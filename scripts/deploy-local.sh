#!/bin/bash

set -e  

echo "🚀 Starting CI/CD Pipeline for Local Kubernetes"

# 
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 
echo -e "${YELLOW}📋 Step 1: Running tests...${NC}"

# 创建临时虚拟环境用于测试
TEMP_VENV=$(mktemp -d)
python3 -m venv "$TEMP_VENV" || { echo -e "${RED}❌ Failed to create virtual environment${NC}"; exit 1; }
source "$TEMP_VENV/bin/activate" || { echo -e "${RED}❌ Failed to activate virtual environment${NC}"; exit 1; }

echo "Testing user-service..."
cd services/user-service
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet || { echo -e "${RED}❌ Failed to install dependencies for user-service${NC}"; deactivate; rm -rf "$TEMP_VENV"; exit 1; }
pytest tests/ -v || { echo -e "${RED}❌ User service tests failed${NC}"; deactivate; rm -rf "$TEMP_VENV"; exit 1; }
cd ../..

echo "Testing order-service..."
cd services/order-service
pip install -r requirements.txt --quiet || { echo -e "${RED}❌ Failed to install dependencies for order-service${NC}"; deactivate; rm -rf "$TEMP_VENV"; exit 1; }
pytest tests/ -v || { echo -e "${RED}❌ Order service tests failed${NC}"; deactivate; rm -rf "$TEMP_VENV"; exit 1; }
cd ../..

# 清理虚拟环境
deactivate
rm -rf "$TEMP_VENV"

echo -e "${GREEN}✅ All tests passed${NC}"

# 步骤 2: 构建 Docker 镜像
echo -e "${YELLOW}🔨 Step 2: Building Docker images...${NC}"
docker build -t user-service:latest ./services/user-service || { echo -e "${RED}❌ Failed to build user-service${NC}"; exit 1; }
docker build -t order-service:latest ./services/order-service || { echo -e "${RED}❌ Failed to build order-service${NC}"; exit 1; }

echo -e "${GREEN}✅ Images built successfully${NC}"

# 步骤 3: 验证 Kubernetes 集群
echo -e "${YELLOW}🔍 Step 3: Verifying Kubernetes cluster...${NC}"
kubectl cluster-info || { echo -e "${RED}❌ Kubernetes cluster not accessible${NC}"; exit 1; }
kubectl get nodes || { echo -e "${RED}❌ Cannot connect to Kubernetes cluster${NC}"; exit 1; }

echo -e "${GREEN}✅ Kubernetes cluster accessible${NC}"

# 步骤 3.5: 清理旧的部署（如果存在）
echo -e "${YELLOW}🧹 Step 3.5: Cleaning up existing deployments...${NC}"
if kubectl get deployment user-service &>/dev/null || kubectl get deployment order-service &>/dev/null; then
    echo "Removing existing deployments..."
    kubectl delete -k k8s/ --ignore-not-found=true || true
    echo "Waiting for resources to be deleted..."
    sleep 5
    echo -e "${GREEN}✅ Old deployments cleaned up${NC}"
else
    echo "No existing deployments found, skipping cleanup"
fi

# 步骤 4: 部署到 Kubernetes
echo -e "${YELLOW}🚢 Step 4: Deploying to Kubernetes...${NC}"
kubectl apply -k k8s/ || { echo -e "${RED}❌ Deployment failed${NC}"; exit 1; }

# 步骤 5: 等待部署完成
echo -e "${YELLOW}⏳ Step 5: Waiting for deployment to complete...${NC}"
kubectl rollout status deployment/user-service --timeout=5m || { echo -e "${RED}❌ User service deployment failed${NC}"; exit 1; }
kubectl rollout status deployment/order-service --timeout=5m || { echo -e "${RED}❌ Order service deployment failed${NC}"; exit 1; }

echo -e "${GREEN}✅ Deployment completed${NC}"

# 步骤 6: 验证部署
echo -e "${YELLOW}✅ Step 6: Verifying deployment...${NC}"
echo "Pods:"
kubectl get pods

echo ""
echo "Services:"
kubectl get services

echo ""
echo "Deployments:"
kubectl get deployments

# 步骤 7: 测试服务
echo -e "${YELLOW}🧪 Step 7: Testing services...${NC}"

# 测试 user-service
echo "Testing user-service..."
kubectl port-forward service/user-service 8000:8000 &
PF_USER_PID=$!
sleep 5

if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ User service is healthy${NC}"
else
    echo -e "${RED}❌ User service health check failed${NC}"
    kill $PF_USER_PID 2>/dev/null || true
    exit 1
fi

kill $PF_USER_PID 2>/dev/null || true

# 测试 order-service
echo "Testing order-service..."
kubectl port-forward service/order-service 8001:8000 &
PF_ORDER_PID=$!
sleep 5

if curl -f http://localhost:8001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Order service is healthy${NC}"
else
    echo -e "${RED}❌ Order service health check failed${NC}"
    kill $PF_ORDER_PID 2>/dev/null || true
    exit 1
fi

kill $PF_ORDER_PID 2>/dev/null || true

echo -e "${GREEN}🎉 CI/CD Pipeline completed successfully!${NC}"
echo ""
echo "Services are now running in Kubernetes."
echo "To access services, use port-forwarding:"
echo "  kubectl port-forward service/user-service 8000:8000"
echo "  kubectl port-forward service/order-service 8001:8000"

