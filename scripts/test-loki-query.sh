#!/bin/bash

# 测试脚本：生成日志并查询 Loki

echo "🔍 测试 Loki 日志查询"

# 1. 生成一些测试日志
echo "📝 生成测试日志..."
kubectl port-forward service/user-service 8000:8000 > /dev/null 2>&1 &
PF_PID=$!
sleep 2

for i in {1..5}; do
  curl -s http://localhost:8000/users > /dev/null
  echo "  ✓ 请求 $i 已发送"
  sleep 1
done

kill $PF_PID 2>/dev/null

# 2. 等待日志转发
echo ""
echo "⏳ 等待日志转发（15秒）..."
sleep 15

# 3. 查询 Loki
echo ""
echo "🔍 查询 Loki..."
kubectl port-forward service/loki 3100:3100 > /dev/null 2>&1 &
LOKI_PF_PID=$!
sleep 3

# 检查标签
echo "检查可用标签..."
curl -s "http://localhost:3100/loki/api/v1/labels" 2>/dev/null | jq -r '.data[]' 2>/dev/null | head -5

# 查询日志
echo ""
echo "查询日志..."
curl -G -s "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={app="user-service"}' \
  --data-urlencode 'limit=10' \
  --data-urlencode "start=$(($(date +%s) - 300))000000000" \
  --data-urlencode "end=$(date +%s)000000000" 2>/dev/null | jq '.data.result | length' 2>/dev/null

kill $LOKI_PF_PID 2>/dev/null

echo ""
echo "✅ 测试完成！现在可以在 Grafana Explore 中查询："
echo "   {app=\"user-service\"}"

