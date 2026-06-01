# ============================================================
# knowledge.kb_chunks — 文档分块表 ORM 模型
# ============================================================

import uuid

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class KbChunk(Base):  # type: ignore[misc]
    """文档分块表"""

    __tablename__ = "kb_chunks"
    __table_args__ = {"schema": "knowledge"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id = Column(UUID(as_uuid=True), nullable=False)

    # 分块内容
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page_no = Column(Integer, nullable=True)
    section_title = Column(String(256), nullable=True)

    # 分块元数据
    token_count = Column(Integer, nullable=False)
    char_count = Column(Integer, nullable=False)
    chunk_type = Column(String(16), nullable=False, default="TEXT")

    # Milvus 向量引用
    milvus_id = Column(String(128), nullable=True)
    embedding_model = Column(String(64), nullable=True)
    embedded_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
