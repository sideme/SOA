#!/bin/bash

echo "=== Kubernetes Networking, Scaling, and Service Discovery Verification ==="
echo ""

echo "1. Checking Pod Status..."
kubectl get pods
echo ""

echo "2. Checking Services..."
kubectl get services
echo ""

echo "3. Checking Service Endpoints..."
kubectl get endpoints
echo ""

echo "4. Testing Service Discovery (DNS)..."
ORDER_POD=$(kubectl get pods -l app=order-service -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -n "$ORDER_POD" ]; then
  echo "Testing from order-service pod: $ORDER_POD"
  kubectl exec $ORDER_POD -- wget -O- -q http://user-service:8000/health 2>/dev/null && echo "✓ Service discovery working!" || echo "✗ Service discovery failed"
else
  echo "No order-service pods found"
fi
echo ""

echo "5. Testing Cross-Service Communication..."
if [ -n "$ORDER_POD" ]; then
  kubectl exec $ORDER_POD -- curl -s http://user-service:8000/health 2>/dev/null && echo "✓ Cross-service communication working!" || echo "✗ Cross-service communication failed"
else
  echo "No order-service pods found"
fi
echo ""

echo "6. Checking HPA Status..."
kubectl get hpa 2>/dev/null || echo "HPA not configured yet (run: kubectl apply -f k8s/user-service/hpa.yaml)"
echo ""

echo "7. Checking Current Resource Usage..."
kubectl top pods 2>/dev/null || echo "Metrics not available (metrics-server may not be installed)"
echo ""

echo "8. Testing End-to-End Flow..."
kubectl port-forward service/user-service 8000:8000 > /dev/null 2>&1 &
USER_PF=$!
kubectl port-forward service/order-service 8001:8000 > /dev/null 2>&1 &
ORDER_PF=$!
sleep 3

USER_RESPONSE=$(curl -s -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"name": "E2E Test", "email": "e2e@example.com"}' 2>/dev/null)
USER_ID=$(echo $USER_RESPONSE | grep -o '"id":"[^"]*' | cut -d'"' -f4)

if [ -n "$USER_ID" ]; then
  ORDER_RESPONSE=$(curl -s -X POST http://localhost:8001/orders \
    -H "Content-Type: application/json" \
    -d "{\"user_id\": \"$USER_ID\", \"items\": [{\"sku\": \"E2E-001\", \"quantity\": 1, \"unit_price\": 10.00}]}" 2>/dev/null)

  if echo "$ORDER_RESPONSE" | grep -q "total_amount"; then
    echo "✓ End-to-end test PASSED - Service discovery working!"
  else
    echo "✗ End-to-end test FAILED"
    echo "Response: $ORDER_RESPONSE"
  fi
else
  echo "✗ Failed to create user"
fi

kill $USER_PF $ORDER_PF 2>/dev/null
echo ""

echo "=== Verification Complete ==="

