# AI 智能投标系统 · 本地开发基础设施

> Story: **S0-002** | 目标：`docker compose up` 一键启动全部基础服务

---

## 包含服务

| 服务 | 版本 | 端口 | 用途 |
|---|---|---|---|
| PostgreSQL | 15-alpine | 5432 | 业务关系数据库（6 个 Schema） |
| Redis | 7-alpine | 6379 | 缓存 / Session / Celery Broker |
| Elasticsearch | 8.11.0 + IK | 9200 | 全文检索（含 IK 中文分词器） |
| MinIO | RELEASE.2024-04 | 9000 (API) / 9001 (Console) | 项目对象存储 |
| Milvus | v2.4.5 standalone | 19530 | 向量数据库 |
| etcd | v3.5.5 | — | Milvus 元数据（不暴露宿主机端口） |
| milvus-minio | RELEASE.2023-03 | — | Milvus 内部存储（不暴露宿主机端口） |

---

## 快速开始

### 1. 准备环境变量

```bash
cp .env.example .env
# 按需修改 .env 中的密码和端口
```

### 2. 一键启动

```bash
docker compose -f docker-compose.dev.yml up -d
```

首次启动会：
1. 拉取或构建所需镜像（ES 需要构建以安装 IK 插件）
2. 自动创建 Named Volumes 持久化数据
3. PostgreSQL 自动执行 `postgres/init/01-init.sql`，创建 6 个 Schema 和必要扩展
4. MinIO 自动创建 4 个私有 Bucket：`bid-raw-files` / `bid-exports` / `kb-documents` / `audit-logs`

### 3. 查看服务状态

```bash
# 查看所有容器健康状态
docker compose -f docker-compose.dev.yml ps

# 查看实时日志
docker compose -f docker-compose.dev.yml logs -f

# 仅查看不健康服务
docker compose -f docker-compose.dev.yml ps | grep -v healthy
```

### 4. 健康检查验证

```bash
# PostgreSQL
docker exec bidai-postgres pg_isready -U bidai -d bidai

# Redis
docker exec bidai-redis redis-cli -a bidai_redis_pass ping

# Elasticsearch
curl http://localhost:9200/_cluster/health

# MinIO
curl http://localhost:9000/minio/health/live

# Milvus
curl http://localhost:9091/healthz
```

### 5. 停止与清理

```bash
# 停止服务（保留数据卷）
docker compose -f docker-compose.dev.yml down

# 停止并删除数据卷（彻底重置）
docker compose -f docker-compose.dev.yml down -v
```

---

## 连接信息

### PostgreSQL
```
Host:     localhost:5432
Database: bidai
User:     bidai
Password: bidai_dev_pass（以 .env 为准）
Schemas:  auth, project, knowledge, bid, ai_task, audit
```

### Redis
```
Host:     localhost:6379
Password: bidai_redis_pass（以 .env 为准）
DB:       0
```

### Elasticsearch
```
Host:     http://localhost:9200
Auth:     无（开发环境关闭 xpack.security）
Plugins:  analysis-ik
```

### MinIO
```
API:      http://localhost:9000
Console:  http://localhost:9001
RootUser: minioadmin
RootPass: minioadmin（以 .env 为准）
```

### Milvus
```
Host:     localhost:19530
```

---

## 数据持久化

所有服务数据均通过 Docker Named Volume 持久化，容器重启/重建不会丢失：

| Volume | 服务 | 宿主机路径 |
|---|---|---|
| `postgres_data` | PostgreSQL | Docker 管理 |
| `redis_data` | Redis | Docker 管理 |
| `es_data` | Elasticsearch | Docker 管理 |
| `minio_data` | MinIO | Docker 管理 |
| `etcd_data` | etcd | Docker 管理 |
| `milvus_minio_data` | Milvus 内部 MinIO | Docker 管理 |
| `milvus_data` | Milvus | Docker 管理 |

如需查看实际存储位置：
```bash
docker volume inspect infra/docker_postgres_data
```

---

## 注意事项

1. **端口冲突**：如果本地已运行同名服务（如本地 PostgreSQL），请修改 `.env` 中的 `*_PORT` 映射。
2. **内存要求**：Milvus + ES 建议宿主机至少 **4GB 可用内存**。
3. **ES 构建**：首次启动 ES 需要从 GitHub 下载 IK 插件，国内网络可能较慢，建议配置 Docker 代理或等待重试。
4. **Milvus 启动时间**：Milvus standalone 首次初始化可能需要 **1~2 分钟**，请耐心等待 `healthy` 状态。
5. **安全提醒**：`.env` 文件已加入 `.gitignore`，切勿将真实密码提交到 Git。

---

## 故障排查

| 现象 | 原因 | 解决 |
|---|---|---|
| ES 启动失败 `plugin install` 超时 | 下载 IK 插件网络不通 | 配置 Docker 代理，或手动下载插件后修改 Dockerfile |
| Milvus 一直 `starting` | 依赖 etcd/minio 未就绪 | 等待 2~3 分钟，Milvus 有 60s 的 start_period |
| PostgreSQL 初始化脚本未执行 | 数据库已存在（volume 残留） | `docker compose down -v` 后重新启动 |
| 端口被占用 | 本地已有同类服务 | 修改 `.env` 中对应端口 |

---

*本文档随 Sprint 0 基础设施搭建同步产出，后续如增减服务请同步更新。*
