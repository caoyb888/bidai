#!/bin/bash
# ============================================================
# AI 智能投标系统 · 本地开发基础设施健康检查脚本
# Story: S0-002
# 用法：./health-check.sh
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILED=0

check_service() {
    local name="$1"
    local cmd="$2"
    local expect="$3"

    printf "%-30s" "Checking $name ..."
    if result=$(eval "$cmd" 2>&1); then
        if [[ "$result" == *"$expect"* ]]; then
            echo -e "${GREEN}OK${NC}"
            return 0
        else
            echo -e "${YELLOW}WARN${NC} (unexpected output: $result)"
            return 0
        fi
    else
        echo -e "${RED}FAIL${NC} ($result)"
        FAILED=1
        return 1
    fi
}

echo "=========================================="
echo " BidAI 本地开发基础设施健康检查"
echo "=========================================="
echo ""

# 1. PostgreSQL
check_service \
    "PostgreSQL" \
    'docker exec bidai-postgres pg_isready -U bidai -d bidai' \
    "accepting connections"

# 2. Redis
check_service \
    "Redis" \
    'docker exec bidai-redis redis-cli -a bidai_redis_pass ping' \
    "PONG"

# 3. Elasticsearch
check_service \
    "Elasticsearch" \
    'curl -fsS http://localhost:9200/_cluster/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[\"status\"])"' \
    "green"

# 4. MinIO
check_service \
    "MinIO" \
    'bash -c "exec 3<>/dev/tcp/localhost/9000 && printf \"GET /minio/health/live HTTP/1.1\\r\\nHost: localhost\\r\\nConnection: close\\r\\n\\r\\n\" >&3 && read -r line <&3 && echo \"\$line\""' \
    "200 OK"

# 5. Milvus
check_service \
    "Milvus" \
    'curl -fsS http://localhost:9091/healthz' \
    "OK"

# 6. etcd (Milvus 依赖)
check_service \
    "etcd" \
    'docker exec bidai-etcd etcdctl endpoint health' \
    "healthy"

echo ""
echo "=========================================="
if [ "$FAILED" -eq 0 ]; then
    echo -e "  ${GREEN}全部服务健康检查通过 ✅${NC}"
    echo "=========================================="
    exit 0
else
    echo -e "  ${RED}部分服务检查失败，请查看日志 ❌${NC}"
    echo "=========================================="
    exit 1
fi
