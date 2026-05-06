# ============================================================
# knowledge.kb_documents — 知识库文档 ORM 模型
# ============================================================

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from app.models.base import BaseModel

if TYPE_CHECKING:
    pass


class KbDocument(BaseModel):
    """知识库文档主表"""

    __tablename__ = "kb_documents"
    __table_args__ = {"schema": "knowledge"}

    project_id = Column(UUID(as_uuid=True), nullable=True)
    doc_type = Column(String(32), nullable=False)
    title = Column(String(512), nullable=False)
    file_path = Column(String(1024), nullable=False)
    file_name = Column(String(256), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    mime_type = Column(String(128), nullable=False)
    file_hash = Column(String(64), nullable=False, unique=True)

    # 解析状态
    parse_status = Column(String(16), nullable=False, default="PENDING")
    parse_error = Column(Text, nullable=True)
    parsed_at = Column(DateTime(timezone=True), nullable=True)

    # 内容信息
    page_count = Column(Integer, nullable=True)
    word_count = Column(Integer, nullable=True)
    language = Column(String(8), nullable=True, default="zh-CN")

    # 分类与标签
    industry = Column(String(64), nullable=True)
    region = Column(String(64), nullable=True)
    tags = Column(ARRAY(Text), nullable=True, default=list)  # type: ignore[var-annotated]
    keywords = Column(ARRAY(Text), nullable=True, default=list)  # type: ignore[var-annotated]

    # 置信度与质量
    confidence = Column(Float, nullable=False, default=0.0)
    quality_score = Column(Float, nullable=True)
    ingest_mode = Column(String(16), nullable=False, default="AUTO")

    # 有效期管理
    effective_date = Column(Date, nullable=True)
    expire_date = Column(Date, nullable=True)
    is_expired = Column(Boolean, nullable=False, default=False)

    # 解析后文本存储路径（MinIO）
    parsed_text_path = Column(String(1024), nullable=True)

    # ES / Milvus 同步状态
    es_indexed = Column(Boolean, nullable=False, default=False)
    es_indexed_at = Column(DateTime(timezone=True), nullable=True)
    milvus_synced = Column(Boolean, nullable=False, default=False)
    milvus_synced_at = Column(DateTime(timezone=True), nullable=True)
