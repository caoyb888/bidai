# bid-review-service

AI 智能投标系统 — **投标审查服务**

## 技术栈

- Python 3.11 + FastAPI 0.110+
- SQLAlchemy 2.0 + asyncpg（异步 PostgreSQL）
- Celery + Redis（异步任务队列）
- Alembic（数据库迁移）
- Poetry（依赖管理）

## 开发命令

```bash
# 安装依赖
poetry install

# 启动开发服务器
poetry run uvicorn app.main:app --reload --port 8003

# 运行测试
poetry run pytest tests/ -v --cov=app --cov-report=html

# 代码格式化
poetry run black app/ && poetry run ruff check app/ --fix

# 类型检查
poetry run mypy app/

# 数据库迁移
poetry run alembic revision --autogenerate -m "描述"
poetry run alembic upgrade head

# 启动 Celery Worker
poetry run celery -A app.worker worker --loglevel=info
```

## 项目结构

遵循 CLAUDE.md 规范：

```
app/
├── api/v1/        # FastAPI 路由层
├── core/          # 配置 / 日志 / 异常 / 安全
├── models/        # Pydantic 数据模型
├── schemas/       # 数据库 ORM 模型
├── services/      # 业务逻辑层
├── repositories/  # 数据访问层
├── ai/            # AI 能力封装（LLM/RAG/OCR）
├── utils/         # 工具函数
└── worker.py      # Celery Worker 入口
```
