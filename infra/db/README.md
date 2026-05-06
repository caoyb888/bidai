# 数据库迁移管理

**Story**: S0-008 — 数据库 Schema 初始化迁移脚本

---

## 目录结构

```
infra/db/
├── alembic.ini              # Alembic 配置文件
├── env.py                   # Alembic 环境脚本
├── migrations/
│   └── V001__init_schema.sql  # 初始基线迁移（全部 6 个 Schema）
├── versions/
│   └── 9d30203ca4c7_init_schema.py  # Alembic revision（执行 SQL 文件）
└── README.md                # 本文档
```

---

## 技术选型

| 工具 | 版本 | 用途 |
|------|------|------|
| Alembic | 1.16+ | 迁移编排（`upgrade`/`downgrade`/`history`） |
| PostgreSQL | 15+ | 数据库引擎 |
| psycopg2 | 2.9+ | Python 驱动 |

---

## 快速使用

### 本地开发环境

```bash
# 1. 确保 PostgreSQL 已启动（S0-002）
docker compose -f infra/docker/docker-compose.dev.yml up -d postgres

# 2. 安装依赖
pip install alembic psycopg2-binary sqlparse

# 3. 执行迁移
cd infra/db
alembic upgrade head

# 4. 验证
alembic current
```

### 查看迁移历史

```bash
cd infra/db
alembic history --verbose
```

### 回滚（开发调试用）

```bash
cd infra/db
alembic downgrade base   # 回滚到初始状态（删除全部 Schema）
alembic upgrade head     # 重新执行
```

---

## 配置说明

### 数据库连接

编辑 `alembic.ini`：

```ini
sqlalchemy.url = postgresql+psycopg2://bidai:bidai_dev_pass@localhost:5432/bidai
```

或通过环境变量覆盖：

```bash
export SQLALCHEMY_URL="postgresql+psycopg2://user:pass@host:5432/db"
sed -i "s|sqlalchemy.url = .*|sqlalchemy.url = $SQLALCHEMY_URL|" alembic.ini
```

---

## Schema 覆盖范围

| Schema | 说明 | 核心表 |
|--------|------|--------|
| `auth` | 用户与权限 | users, roles, permissions, user_roles, refresh_tokens |
| `project` | 项目管理 | bid_projects, project_members, bid_records |
| `knowledge` | 知识库 | kb_documents, kb_chunks, qualifications, performances, personnel |
| `bid` | 标书编写 | bids, bid_sections, section_versions, bid_variables, bid_check_reports |
| `ai_task` | AI 任务 | ai_tasks, doc_constraints, review_tasks, review_items, collusion_analysis_tasks |
| `audit` | 审计日志 | audit_logs, export_logs, llm_call_logs |

---

## 设计调整说明

本迁移脚本基于 `docs/database-design.md` 自动生成，针对 PostgreSQL 15 做了以下必要调整：

1. **`is_expired` 计算列**：原设计使用 `GENERATED ALWAYS AS (expire_date < CURRENT_DATE) STORED`，但 `CURRENT_DATE` 是 `STABLE` 函数，不能用于 generated column。已改为 `BOOLEAN NOT NULL DEFAULT FALSE`，后续通过定时任务或触发器维护。

2. **`section_versions` 主键**：分区表的主键必须包含分区键。已将 `PRIMARY KEY (id)` 调整为 `PRIMARY KEY (id, created_at)`，唯一约束同步调整。

3. **部分索引 `CURRENT_DATE`**：原设计在部分索引 WHERE 子句中使用 `CURRENT_DATE + INTERVAL`，但 `CURRENT_DATE` 非 `IMMUTABLE`。已简化为 `expire_date IS NOT NULL` 的范围索引。

---

## 后续增量迁移

各服务开发自己的增量迁移时：

- **Python 服务**：在 `{service}/migrations/` 下使用 Alembic
- **Java 服务**：在 `src/main/resources/db/migration/` 下使用 Flyway
- 所有 DDL 变更须同步更新 `docs/database-design.md`
