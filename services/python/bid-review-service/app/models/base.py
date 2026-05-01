# ============================================================
# ORM 基类 — 与数据库设计文档对齐
# 所有业务表必须包含：id/created_at/updated_at/deleted_at/created_by/updated_by
# ============================================================

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class BaseModel(Base):  # type: ignore[misc]
    """业务表公共字段基类"""

    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(64), nullable=False, default="system")
    updated_by = Column(String(64), nullable=False, default="system")
