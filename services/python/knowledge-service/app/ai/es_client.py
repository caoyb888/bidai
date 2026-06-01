# ============================================================
# Elasticsearch 异步客户端 — 全文检索 + IK 中文分词
# 职责：索引管理、文档索引、全文搜索、高亮、按 doc_id 删除
# ============================================================

from __future__ import annotations

from typing import Any

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

from app.core.config import settings
from app.core.logging import logger


class ESError(Exception):
    """Elasticsearch 操作异常"""


class ESClient:
    """Elasticsearch 异步客户端封装（单例）"""

    _instance: ESClient | None = None
    _client: AsyncElasticsearch | None = None

    def __new__(cls) -> ESClient:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_client(self) -> AsyncElasticsearch:
        """获取或创建 ES 客户端"""
        if ESClient._client is None:
            auth: tuple[str, str] | None = None
            if settings.es_username and settings.es_password:
                auth = (settings.es_username, settings.es_password)
            ESClient._client = AsyncElasticsearch(
                [settings.es_url],
                basic_auth=auth,
                retry_on_timeout=True,
                max_retries=3,
                request_timeout=30,
            )
        return ESClient._client

    async def close(self) -> None:
        """关闭 ES 连接"""
        if ESClient._client is not None:
            await ESClient._client.close()
            ESClient._client = None

    async def ensure_index(self) -> None:
        """确保索引存在，使用 IK 分词器"""
        client = self._get_client()
        index = settings.es_index

        exists = await client.indices.exists(index=index)
        if exists:
            return

        logger.info("Creating Elasticsearch index", extra={"index": index})

        mapping: dict[str, Any] = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "ik_analyzer": {
                            "type": "custom",
                            "tokenizer": "ik_max_word",
                            "filter": ["lowercase"],
                        },
                    },
                },
            },
            "mappings": {
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "doc_id": {"type": "keyword"},
                    "content": {
                        "type": "text",
                        "analyzer": "ik_analyzer",
                        "search_analyzer": "ik_smart",
                        "store": True,
                    },
                    "chunk_type": {"type": "keyword"},
                    "page_no": {"type": "integer"},
                    "section_title": {
                        "type": "text",
                        "analyzer": "ik_analyzer",
                        "search_analyzer": "ik_smart",
                    },
                    "doc_title": {
                        "type": "text",
                        "analyzer": "ik_analyzer",
                        "search_analyzer": "ik_smart",
                    },
                    "tags": {"type": "keyword"},
                },
            },
        }

        try:
            await client.indices.create(index=index, body=mapping)
            logger.info("Elasticsearch index created", extra={"index": index})
        except Exception as exc:
            logger.error("ES index creation failed", extra={"error": str(exc)})
            raise ESError(f"ES index creation failed: {exc}") from exc

    async def index_chunk(
        self,
        chunk_id: str,
        doc_id: str,
        content: str,
        chunk_type: str,
        page_no: int | None,
        section_title: str | None,
        doc_title: str,
        tags: list[str] | None = None,
    ) -> None:
        """索引单个 chunk"""
        client = self._get_client()
        index = settings.es_index

        body: dict[str, Any] = {
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "content": content,
            "chunk_type": chunk_type,
            "page_no": page_no,
            "section_title": section_title or "",
            "doc_title": doc_title,
            "tags": tags or [],
        }

        try:
            await client.index(index=index, id=chunk_id, body=body, refresh=False)
        except Exception as exc:
            logger.error("ES index chunk failed", extra={"chunk_id": chunk_id, "error": str(exc)})
            raise ESError(f"ES index chunk failed: {exc}") from exc

    async def bulk_index_chunks(
        self,
        chunks: list[dict[str, Any]],
    ) -> None:
        """批量索引 chunks"""
        if not chunks:
            return

        client = self._get_client()
        index = settings.es_index

        actions = [
            {
                "_index": index,
                "_id": chunk["chunk_id"],
                "_source": chunk,
            }
            for chunk in chunks
        ]

        try:
            success, errors = await async_bulk(client, actions, refresh=False, raise_on_error=False)
            if isinstance(errors, list) and errors:
                logger.warning("ES bulk index partial failure", extra={"success": success, "errors": len(errors)})
            else:
                logger.info("ES bulk index completed", extra={"success": success})
        except Exception as exc:
            logger.error("ES bulk index failed", extra={"error": str(exc)})
            raise ESError(f"ES bulk index failed: {exc}") from exc

    async def search(
        self,
        query: str,
        top_k: int = 50,
        doc_ids: list[str] | None = None,
        doc_category: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        全文检索（IK 分词）

        Returns:
            结果列表，每项包含 chunk_id, doc_id, content, score, highlight
        """
        client = self._get_client()
        index = settings.es_index

        must_clauses: list[dict[str, Any]] = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["content^3", "section_title^2", "doc_title"],
                    "type": "best_fields",
                }
            }
        ]

        filter_clauses: list[dict[str, Any]] = []
        if doc_ids:
            filter_clauses.append({"terms": {"doc_id": doc_ids}})

        if doc_category:
            filter_clauses.append({"term": {"tags": doc_category}})

        body: dict[str, Any] = {
            "size": top_k,
            "query": {
                "bool": {
                    "must": must_clauses,
                    "filter": filter_clauses,
                }
            },
            "highlight": {
                "fields": {
                    "content": {"fragment_size": 150, "number_of_fragments": 1},
                },
                "pre_tags": ['<em class="highlight">'],
                "post_tags": ["</em>"],
            },
            "_source": ["chunk_id", "doc_id", "content", "chunk_type", "page_no", "section_title", "doc_title"],
        }

        try:
            resp = await client.search(index=index, body=body)
        except Exception as exc:
            logger.error("ES search failed", extra={"query": query, "error": str(exc)})
            raise ESError(f"ES search failed: {exc}") from exc

        hits: list[dict[str, Any]] = []
        for hit in resp["hits"]["hits"]:
            highlight_list: list[str] = hit.get("highlight", {}).get("content", [])
            highlight: str = highlight_list[0] if highlight_list else ""
            hits.append(
                {
                    "chunk_id": hit["_source"]["chunk_id"],
                    "doc_id": hit["_source"]["doc_id"],
                    "content": hit["_source"]["content"],
                    "chunk_type": hit["_source"]["chunk_type"],
                    "page_no": hit["_source"].get("page_no"),
                    "section_title": hit["_source"].get("section_title"),
                    "doc_title": hit["_source"].get("doc_title", ""),
                    "score": float(hit["_score"]),
                    "highlight": highlight,
                }
            )

        logger.info("ES search completed", extra={"query": query, "hits": len(hits)})
        return hits

    async def delete_by_doc_id(self, doc_id: str) -> int:
        """根据 doc_id 删除索引文档，返回删除数量"""
        client = self._get_client()
        index = settings.es_index

        body = {
            "query": {
                "term": {"doc_id": doc_id}
            }
        }

        try:
            resp = await client.delete_by_query(index=index, body=body, refresh=False)
            deleted = int(resp.get("deleted", 0))
            logger.info("ES delete by doc_id", extra={"doc_id": doc_id, "deleted": deleted})
            return deleted
        except Exception as exc:
            logger.error("ES delete failed", extra={"doc_id": doc_id, "error": str(exc)})
            raise ESError(f"ES delete failed: {exc}") from exc
