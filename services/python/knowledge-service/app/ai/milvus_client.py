# ============================================================
# Milvus 向量数据库客户端封装
# ============================================================

from typing import Any

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from app.core.config import settings
from app.core.logging import logger


class MilvusError(Exception):
    """Milvus 操作异常"""


class MilvusClient:
    """Milvus 客户端封装"""

    _connected: bool = False

    def __init__(self) -> None:
        self.host = settings.milvus_host
        self.port = settings.milvus_port
        self.collection_name = settings.milvus_collection
        self.dim = settings.embedding_dim
        self._collection: Collection | None = None

    def _ensure_connection(self) -> None:
        """确保 Milvus 连接已建立"""
        if not MilvusClient._connected:
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port,
                user=settings.milvus_username or "",
                password=settings.milvus_password or "",
            )
            MilvusClient._connected = True

    def _ensure_collection(self) -> Collection:
        """确保 Collection 存在并加载"""
        if self._collection is not None:
            return self._collection

        self._ensure_connection()

        if not utility.has_collection(self.collection_name):
            logger.info(
                "Creating Milvus collection",
                extra={"collection": self.collection_name, "dim": self.dim},
            )
            fields = [
                FieldSchema(
                    name="milvus_id",
                    dtype=DataType.VARCHAR,
                    is_primary=True,
                    max_length=128,
                    description="Chunk 在 Milvus 中的唯一标识",
                ),
                FieldSchema(
                    name="doc_id",
                    dtype=DataType.VARCHAR,
                    max_length=128,
                    description="关联文档 ID",
                ),
                FieldSchema(
                    name="chunk_id",
                    dtype=DataType.VARCHAR,
                    max_length=128,
                    description="Chunk 在 PostgreSQL 中的 ID",
                ),
                FieldSchema(
                    name="embedding",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=self.dim,
                    description="向量嵌入",
                ),
                FieldSchema(
                    name="chunk_type",
                    dtype=DataType.VARCHAR,
                    max_length=16,
                    description="TEXT / TABLE",
                ),
            ]
            schema = CollectionSchema(
                fields=fields,
                description="Knowledge base chunks vector collection",
                enable_dynamic_field=False,
            )
            collection = Collection(name=self.collection_name, schema=schema)

            # 创建向量索引（AUTOINDEX 自动选择最优索引）
            index_params = {
                "metric_type": "COSINE",
                "index_type": "AUTOINDEX",
                "params": {},
            }
            collection.create_index(field_name="embedding", index_params=index_params)
            logger.info("Milvus index created", extra={"collection": self.collection_name})
        else:
            collection = Collection(self.collection_name)

        collection.load()
        self._collection = collection
        return collection

    def insert_chunks(
        self,
        milvus_ids: list[str],
        doc_ids: list[str],
        chunk_ids: list[str],
        embeddings: list[list[float]],
        chunk_types: list[str],
    ) -> None:
        """批量插入向量数据"""
        if not milvus_ids:
            return

        collection = self._ensure_collection()

        if len(milvus_ids) != len(embeddings):
            raise MilvusError("milvus_ids and embeddings length mismatch")

        data = [
            milvus_ids,
            doc_ids,
            chunk_ids,
            embeddings,
            chunk_types,
        ]

        try:
            insert_result = collection.insert(data)
            logger.info(
                "Milvus insert completed",
                extra={
                    "insert_count": insert_result.insert_count,
                    "collection": self.collection_name,
                },
            )
        except Exception as exc:
            logger.error("Milvus insert failed", extra={"error": str(exc)})
            raise MilvusError(f"Milvus insert failed: {exc}") from exc

    def delete_by_doc_id(self, doc_id: str) -> None:
        """根据 doc_id 删除所有关联向量"""
        collection = self._ensure_collection()
        expr = f'doc_id == "{doc_id}"'
        try:
            collection.delete(expr)
            logger.info("Milvus delete by doc_id", extra={"doc_id": doc_id})
        except Exception as exc:
            logger.error("Milvus delete failed", extra={"doc_id": doc_id, "error": str(exc)})
            raise MilvusError(f"Milvus delete failed: {exc}") from exc

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        doc_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """向量相似度搜索"""
        collection = self._ensure_collection()

        search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
        expr = None
        if doc_ids:
            ids_expr = " || ".join([f'doc_id == "{d}"' for d in doc_ids])
            expr = f"({ids_expr})"

        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=["doc_id", "chunk_id", "chunk_type"],
        )

        hits: list[dict[str, Any]] = []
        for result in results:
            for hit in result:
                hits.append(
                    {
                        "milvus_id": hit.id,
                        "doc_id": hit.entity.get("doc_id"),
                        "chunk_id": hit.entity.get("chunk_id"),
                        "chunk_type": hit.entity.get("chunk_type"),
                        "score": hit.score,
                    }
                )
        return hits
