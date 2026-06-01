#!/usr/bin/env bash
# ============================================================
# AI 智能投标系统 · 一键本地开发环境启动脚本
# ============================================================
# 用法:
#   ./start-dev.sh start    # 启动全部服务
#   ./start-dev.sh stop     # 停止全部服务
#   ./start-dev.sh status   # 查看服务状态
#   ./start-dev.sh restart  # 重启全部服务
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ----------------------------------------------------------
# 颜色输出
# ----------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERR]${NC}   $*"; }

# ----------------------------------------------------------
# 配置
# ----------------------------------------------------------
INFRA_DIR="${PROJECT_ROOT}/infra/docker"
JAVA_DIR="${PROJECT_ROOT}/services/java"
PYTHON_DIR="${PROJECT_ROOT}/services/python"
FE_DIR="${PROJECT_ROOT}/frontend/bid-web"

# 端口检查
AUTH_PORT=8081
PROJECT_PORT=8082
KNOWLEDGE_PORT=8005
FE_PORT=5173

# ----------------------------------------------------------
# 工具检查
# ----------------------------------------------------------
check_prerequisites() {
    local missing=()

    command -v docker >/dev/null 2>&1 || missing+=("docker")
    command -v docker-compose >/dev/null 2>&1 || command -v docker >/dev/null 2>&1 || missing+=("docker-compose")
    command -v java >/dev/null 2>&1 || missing+=("java")
    command -v pnpm >/dev/null 2>&1 || missing+=("pnpm")
    command -v uvicorn >/dev/null 2>&1 || missing+=("uvicorn (knowledge-service .venv)")

    if [[ ${#missing[@]} -gt 0 ]]; then
        err "缺少必要工具: ${missing[*]}"
        err "请确保以下环境已就绪:"
        err "  - Docker / Docker Compose"
        err "  - Java 21 (brew install openjdk@21)"
        err "  - pnpm (npm install -g pnpm)"
        err "  - knowledge-service 虚拟环境已激活或 uvicorn 已安装"
        exit 1
    fi
}

# ----------------------------------------------------------
# 端口占用检查
# ----------------------------------------------------------
is_port_in_use() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        lsof -i :"${port}" -sTCP:LISTEN >/dev/null 2>&1
    else
        netstat -tlnp 2>/dev/null | grep -q ":${port} " || ss -tlnp 2>/dev/null | grep -q ":${port} "
    fi
}

# ----------------------------------------------------------
# Docker 基础设施 + Python 服务启动
# ----------------------------------------------------------
start_infra() {
    info "启动 Docker 基础设施与 Python 服务..."
    cd "${INFRA_DIR}"

    # 排除 knowledge-service（改本地启动，Docker 镜像过旧）
    docker compose -f docker-compose.dev.yml up -d \
        postgres redis elasticsearch minio etcd milvus-minio milvus-standalone minio-init \
        bid-parser-service bid-writer-service bid-review-service collusion-analysis-service win-rate-service \
        2>&1 | tail -20

    ok "Docker 服务已启动"
}

# ----------------------------------------------------------
# Java 服务启动
# ----------------------------------------------------------
start_java_services() {
    info "启动 Java 服务..."

    export JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk@21}"
    export PATH="${JAVA_HOME}/bin:${PATH}"

    # auth-service
    if is_port_in_use ${AUTH_PORT}; then
        warn "auth-service (:${AUTH_PORT}) 已在运行，跳过"
    else
        info "启动 auth-service (端口 ${AUTH_PORT})..."
        cd "${JAVA_DIR}/auth-service"
        nohup "${JAVA_HOME}/bin/java" -jar build/libs/auth-service-0.1.0.jar \
            > /tmp/auth-service.log 2>&1 &
        ok "auth-service 已启动 (PID: $!)"
    fi

    # project-service
    if is_port_in_use ${PROJECT_PORT}; then
        warn "project-service (:${PROJECT_PORT}) 已在运行，跳过"
    else
        info "启动 project-service (端口 ${PROJECT_PORT})..."
        cd "${JAVA_DIR}/project-service"
        nohup "${JAVA_HOME}/bin/java" -jar build/libs/project-service-0.1.0.jar \
            > /tmp/project-service.log 2>&1 &
        ok "project-service 已启动 (PID: $!)"
    fi

    # export-service
    if is_port_in_use 8083; then
        warn "export-service (:8083) 已在运行，跳过"
    else
        info "启动 export-service (端口 8083)..."
        cd "${JAVA_DIR}/export-service"
        if [[ -f build/libs/export-service-0.1.0.jar ]]; then
            nohup "${JAVA_HOME}/bin/java" -jar build/libs/export-service-0.1.0.jar \
                > /tmp/export-service.log 2>&1 &
            ok "export-service 已启动 (PID: $!)"
        else
            warn "export-service jar 不存在，跳过（请先执行 ./gradlew build）"
        fi
    fi

    # notify-service
    if is_port_in_use 8084; then
        warn "notify-service (:8084) 已在运行，跳过"
    else
        info "启动 notify-service (端口 8084)..."
        cd "${JAVA_DIR}/notify-service"
        if [[ -f build/libs/notify-service-0.1.0.jar ]]; then
            nohup "${JAVA_HOME}/bin/java" -jar build/libs/notify-service-0.1.0.jar \
                > /tmp/notify-service.log 2>&1 &
            ok "notify-service 已启动 (PID: $!)"
        else
            warn "notify-service jar 不存在，跳过（请先执行 ./gradlew build）"
        fi
    fi
}

# ----------------------------------------------------------
# knowledge-service 本地启动
# ----------------------------------------------------------
start_knowledge_service() {
    info "启动 knowledge-service (本地模式)..."

    if is_port_in_use ${KNOWLEDGE_PORT}; then
        warn "knowledge-service (:${KNOWLEDGE_PORT}) 已在运行，跳过"
        return
    fi

    cd "${PYTHON_DIR}/knowledge-service"

    # 激活虚拟环境
    if [[ -f .venv/bin/activate ]]; then
        source .venv/bin/activate
    else
        err "knowledge-service .venv 不存在，请先执行 poetry install"
        exit 1
    fi

    # 设置本地数据库连接（覆盖 Docker 内部主机名）
    export DATABASE_URL="postgresql+asyncpg://bidai:bidai_dev_pass@localhost:5432/bidai"
    export REDIS_URL="redis://:bidai_redis_pass@localhost:6379/0"

    nohup uvicorn app.main:app --host 0.0.0.0 --port ${KNOWLEDGE_PORT} \
        > /tmp/knowledge-service.log 2>&1 &
    ok "knowledge-service 已启动 (PID: $!, 端口 ${KNOWLEDGE_PORT})"
}

# ----------------------------------------------------------
# 前端启动
# ----------------------------------------------------------
start_frontend() {
    info "启动前端 bid-web..."

    if is_port_in_use ${FE_PORT}; then
        warn "前端 (:${FE_PORT}) 已在运行，跳过"
        return
    fi

    cd "${FE_DIR}"

    if [[ ! -d node_modules ]]; then
        warn "node_modules 不存在，执行 pnpm install..."
        pnpm install
    fi

    nohup pnpm dev > /tmp/bid-web.log 2>&1 &
    ok "前端已启动 (PID: $!, 端口 ${FE_PORT})"
}

# ----------------------------------------------------------
# 等待服务就绪
# ----------------------------------------------------------
wait_for_services() {
    info "等待服务就绪..."
    local max_wait=60
    local waited=0

    while [[ ${waited} -lt ${max_wait} ]]; do
        local ready=0

        curl -sf "http://localhost:${AUTH_PORT}/actuator/health" >/dev/null 2>&1 && ready=$((ready + 1))
        curl -sf "http://localhost:${PROJECT_PORT}/actuator/health" >/dev/null 2>&1 && ready=$((ready + 1))
        curl -sf "http://localhost:${KNOWLEDGE_PORT}/api/v1/health" >/dev/null 2>&1 && ready=$((ready + 1))

        if [[ ${ready} -eq 3 ]]; then
            ok "所有核心服务已就绪 (${waited}s)"
            return
        fi

        sleep 1
        waited=$((waited + 1))
    done

    warn "部分服务启动超时，请检查日志"
}

# ----------------------------------------------------------
# 打印访问地址
# ----------------------------------------------------------
print_endpoints() {
    echo ""
    echo "============================================================"
    echo -e "${GREEN}  AI 智能投标系统 · 开发环境已启动${NC}"
    echo "============================================================"
    echo ""
    echo "  前端界面:       http://localhost:${FE_PORT}/"
    echo "  知识库管理:     http://localhost:${FE_PORT}/knowledge"
    echo ""
    echo "  API 网关:"
    echo "    auth-service:     http://localhost:${AUTH_PORT}"
    echo "    project-service:  http://localhost:${PROJECT_PORT}"
    echo "    knowledge-svc:    http://localhost:${KNOWLEDGE_PORT}"
    echo ""
    echo "  基础设施:"
    echo "    PostgreSQL:       localhost:5432"
    echo "    Redis:            localhost:6379"
    echo "    Elasticsearch:    localhost:9200"
    echo "    MinIO:            localhost:9000 / 9001"
    echo "    Milvus:           localhost:19530"
    echo ""
    echo "  日志文件:"
    echo "    auth-service:     /tmp/auth-service.log"
    echo "    project-service:  /tmp/project-service.log"
    echo "    knowledge-svc:    /tmp/knowledge-service.log"
    echo "    bid-web:          /tmp/bid-web.log"
    echo ""
    echo "  测试账号:"
    echo "    管理员: admin / Admin@123"
    echo ""
    echo "============================================================"
}

# ----------------------------------------------------------
# 停止服务
# ----------------------------------------------------------
stop_services() {
    info "停止全部服务..."

    # 停止前端
    pkill -f "vite" 2>/dev/null || true
    ok "前端已停止"

    # 停止本地 knowledge-service
    pkill -f "uvicorn app.main:app --host 0.0.0.0 --port ${KNOWLEDGE_PORT}" 2>/dev/null || true
    ok "knowledge-service 已停止"

    # 停止 Java 服务
    pkill -f "auth-service-0.1.0.jar" 2>/dev/null || true
    pkill -f "project-service-0.1.0.jar" 2>/dev/null || true
    pkill -f "export-service-0.1.0.jar" 2>/dev/null || true
    pkill -f "notify-service-0.1.0.jar" 2>/dev/null || true
    ok "Java 服务已停止"

    # 停止 Docker
    cd "${INFRA_DIR}"
    docker compose -f docker-compose.dev.yml down 2>&1 | tail -5
    ok "Docker 服务已停止"

    echo ""
    ok "全部服务已停止"
}

# ----------------------------------------------------------
# 查看状态
# ----------------------------------------------------------
show_status() {
    echo "============================================================"
    echo "  服务运行状态"
    echo "============================================================"
    echo ""

    local services=(
        "前端:5173:pnpm dev"
        "auth-service:8081:auth-service-0.1.0.jar"
        "project-service:8082:project-service-0.1.0.jar"
        "knowledge-service:8005:uvicorn app.main:app --host 0.0.0.0 --port 8005"
        "export-service:8083:export-service-0.1.0.jar"
        "notify-service:8084:notify-service-0.1.0.jar"
    )

    for svc in "${services[@]}"; do
        IFS=':' read -r name port pattern <<< "${svc}"
        if is_port_in_use "${port}"; then
            ok "${name} 运行中 (端口 ${port})"
        else
            warn "${name} 未运行 (端口 ${port})"
        fi
    done

    echo ""
    info "Docker 容器状态:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null | grep bidai || echo "  无运行中的 bidai 容器"
}

# ----------------------------------------------------------
# 主入口
# ----------------------------------------------------------
main() {
    case "${1:-start}" in
        start)
            check_prerequisites
            start_infra
            start_java_services
            start_knowledge_service
            start_frontend
            wait_for_services
            print_endpoints
            ;;
        stop)
            stop_services
            ;;
        restart)
            stop_services
            sleep 2
            check_prerequisites
            start_infra
            start_java_services
            start_knowledge_service
            start_frontend
            wait_for_services
            print_endpoints
            ;;
        status)
            show_status
            ;;
        *)
            echo "用法: $0 {start|stop|restart|status}"
            exit 1
            ;;
    esac
}

main "$@"
