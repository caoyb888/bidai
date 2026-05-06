# ============================================================
# ai_task.ai_tasks — AI 异步任务总表 ORM 模型
# ============================================================

import uuid

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class AiTask(Base):  # type: ignore[misc]
    """AI 异步任务总表"""

    __tablename__ = "ai_tasks"
    __table_args__ = {"schema": "ai_task"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 任务标识
    task_type = Column(String(32), nullable=False)
    task_status = Column(String(16), nullable=False, default="PENDING")
    priority = Column(SmallInteger, nullable=False, default=5)

    # 关联实体（多态外键）
    ref_type = Column(String(32), nullable=True)
    ref_id = Column(UUID(as_uuid=True), nullable=True)

    # Celery 任务信息
    celery_task_id = Column(String(128), nullable=True)
    worker_name = Column(String(128), nullable=True)
    queue_name = Column(String(64), nullable=False, default="default")

    # 执行信息
    input_payload = Column(JSON, nullable=False, default=dict)
    result_payload = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(SmallInteger, nullable=False, default=0)
    max_retries = Column(SmallInteger, nullable=False, default=3)

    # 时间追踪
    queued_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # 公共字段
    created_at = Column(DateTime(timezone=True), nullable=False)
    created_by = Column(String(64), nullable=False)
