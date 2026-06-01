# ============================================================
# 混合检索引擎 — HybridRetriever
# 流程：查询增强 → 并行 Milvus + ES → 去重融合 → Cross-Encoder 重排序 → Top-K
# 符合 CLAUDE.md §6.4 RAG 检索规范
# ============================================================

from __future__ import annotations

import asyncio
from typing import Any

from app.ai.embedding import EmbeddingClient, EmbeddingError
from app.ai.es_client import ESClient, ESError
from app.ai.milvus_client import MilvusClient, MilvusError
from app.ai.query_enhancer import QueryEnhancer
from app.ai.reranker import RerankerClient
from app.core.config import settings
from app.core.logging import logger


class HybridRetrieverError(Exception):
    """混合检索异常"""


class SearchResult:
    """检索结果项"""

    def __init__(
        self,
        chunk_id: str,
        doc_id: str,
        doc_title: str,
        content: str,
        page_no: int | None,
        score: float,
        highlight: str = "",
        source: str = "",
    ) -> None:
        self.chunk_id = chunk_id
        self.doc_id = doc_id
        self.doc_title = doc_title
        self.content = content
        self.page_no = page_no
        self.score = score
        self.highlight = highlight
        self.source = source  # "vector" / "fulltext" / "hybrid"


class HybridRetriever:
    """混合检索引擎"""

    def __init__(
        self,
        query_enhancer: QueryEnhancer | None = None,
        embed_client: EmbeddingClient | None = None,
        milvus_client: MilvusClient | None = None,
        es_client: ESClient | None = None,
        reranker: RerankerClient | None = None,
    ) -> None:
        self.query_enhancer = query_enhancer or QueryEnhancer()
        self.embed_client = embed_client or EmbeddingClient()
        self.milvus = milvus_client or MilvusClient()
        self.es = es_client or ESClient()
        self.reranker = reranker or RerankerClient()

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        doc_ids: list[str] | None = None,
        doc_category: str | None = None,
    ) -> list[SearchResult]:
        """
        执行混合检索

        Args:
            query: 用户查询
            top_k: 返回结果数量
            doc_ids: 限定搜索的文档 ID 列表
            doc_category: 限定知识库分类

        Returns:
            按重排序分数降序排列的 SearchResult 列表
        """
        start_time = asyncio.get_event_loop().time()

        # 1. 查询增强
        enhanced_query = await self.query_enhancer.enhance(query)

        # 2. 获取查询向量（使用增强后的查询）
        try:
            embeddings = await self.embed_client.embed([enhanced_query])
            query_embedding = embeddings[0]
        except EmbeddingError as exc:
            logger.error("Embedding failed for search query", extra={"query": query, "error": str(exc)})
            raise HybridRetrieverError(f"Embedding failed: {exc}") from exc

        # 3. 并行检索：Milvus + ES
        # 召回阶段取更多结果，供后续 rerank 使用
        recall_k = min(max(top_k * 5, 20), settings.search_max_top_k)

        vector_task = self._search_milvus(query_embedding, recall_k, doc_ids)
        fulltext_task = self._search_es(enhanced_query, recall_k, doc_ids, doc_category)

        vector_raw, fulltext_raw = await asyncio.gather(
            vector_task,
            fulltext_task,
            return_exceptions=True,
        )

        # 处理异常：任一检索失败不应阻断整体流程
        from typing import cast

        vector_results: list[SearchResult] = []
        fulltext_results: list[SearchResult] = []
        if isinstance(vector_raw, Exception):
            logger.error("Vector search failed", extra={"error": str(vector_raw)})
        else:
            vector_results = cast(list[SearchResult], vector_raw)
        if isinstance(fulltext_raw, Exception):
            logger.error("Fulltext search failed", extra={"error": str(fulltext_raw)})
        else:
            fulltext_results = cast(list[SearchResult], fulltext_raw)

        # 4. 结果融合 + 去重
        merged = self._merge_and_deduplicate(vector_results, fulltext_results)

        if not merged:
            return []

        # 5. Cross-Encoder 重排序
        candidates = [
            {
                "chunk_id": r.chunk_id,
                "content": r.content,
                "score": r.score,
                "doc_id": r.doc_id,
                "doc_title": r.doc_title,
                "page_no": r.page_no,
                "highlight": r.highlight,
                "source": r.source,
            }
            for r in merged
        ]

        reranked = await self.reranker.rerank(
            query=query,
            candidates=candidates,
            top_k=recall_k,
        )

        # 6. 组装最终结果
        results: list[SearchResult] = []
        candidate_map = {c["chunk_id"]: c for c in candidates}

        for rr in reranked:
            cand = candidate_map.get(rr.chunk_id)
            if cand is None:
                continue
            results.append(
                SearchResult(
                    chunk_id=rr.chunk_id,
                    doc_id=str(cand["doc_id"]),
                    doc_title=str(cand.get("doc_title", "")),
                    content=str(cand.get("content", "")),
                    page_no=int(cand["page_no"]) if cand.get("page_no") is not None else None,  # type: ignore[arg-type]
                    score=rr.score,
                    highlight=str(cand.get("highlight", "")),
                    source=str(cand.get("source", "")),
                )
            )

        # 取 top_k
        final_results = results[:top_k]

        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        logger.info(
            "Hybrid retrieval completed",
            extra={
                "query": query,
                "enhanced_query": enhanced_query,
                "vector_hits": len(vector_results),
                "fulltext_hits": len(fulltext_results),
                "merged_hits": len(merged),
                "final_hits": len(final_results),
                "duration_ms": round(duration_ms, 2),
            },
        )

        return final_results

    async def _search_milvus(
        self,
        query_embedding: list[float],
        top_k: int,
        doc_ids: list[str] | None,
    ) -> list[SearchResult]:
        """Milvus 向量检索"""
        try:
            hits = self.milvus.search(
                query_embedding=query_embedding,
                top_k=top_k,
                doc_ids=doc_ids,
            )
        except MilvusError as exc:
            logger.error("Milvus search error", extra={"error": str(exc)})
            raise

        results: list[SearchResult] = []
        for hit in hits:
            results.append(
                SearchResult(
                    chunk_id=hit["chunk_id"],
                    doc_id=hit["doc_id"],
                    doc_title="",  # Milvus 中不存储 doc_title，后续反查补充
                    content="",    # 同样不存储内容，后续反查
                    page_no=None,
                    score=hit["score"],
                    source="vector",
                )
            )
        return results

    async def _search_es(
        self,
        query: str,
        top_k: int,
        doc_ids: list[str] | None,
        doc_category: str | None,
    ) -> list[SearchResult]:
        """ES 全文检索"""
        try:
            hits = await self.es.search(
                query=query,
                top_k=top_k,
                doc_ids=doc_ids,
                doc_category=doc_category,
            )
        except ESError as exc:
            logger.error("ES search error", extra={"error": str(exc)})
            raise

        results: list[SearchResult] = []
        for hit in hits:
            results.append(
                SearchResult(
                    chunk_id=hit["chunk_id"],
                    doc_id=hit["doc_id"],
                    doc_title=hit.get("doc_title", ""),
                    content=hit["content"],
                    page_no=hit.get("page_no"),
                    score=hit["score"] / 100.0 if hit["score"] > 1.0 else hit["score"],  # 归一化 ES 分数
                    highlight=hit.get("highlight", ""),
                    source="fulltext",
                )
            )
        return results

    def _merge_and_deduplicate(
        self,
        vector_results: list[SearchResult],
        fulltext_results: list[SearchResult],
    ) -> list[SearchResult]:
        """融合向量结果和全文结果，按 chunk_id 去重"""
        merged_map: dict[str, SearchResult] = {}

        for r in vector_results:
            if r.chunk_id not in merged_map:
                merged_map[r.chunk_id] = r
            else:
                # 已存在则取更高分
                if r.score > merged_map[r.chunk_id].score:
                    merged_map[r.chunk_id].score = r.score
                merged_map[r.chunk_id].source = "hybrid"

        for r in fulltext_results:
            if r.chunk_id not in merged_map:
                merged_map[r.chunk_id] = r
            else:
                # 已存在则合并信息（ES 通常有 content 和 highlight）
                existing = merged_map[r.chunk_id]
                if r.score > existing.score:
                    existing.score = r.score
                if r.content and not existing.content:
                    existing.content = r.content
                if r.highlight and not existing.highlight:
                    existing.highlight = r.highlight
                if r.doc_title and not existing.doc_title:
                    existing.doc_title = r.doc_title
                existing.source = "hybrid"

        # 按分数降序排列（作为 reranker 的初始顺序参考）
        return sorted(merged_map.values(), key=lambda x: x.score, reverse=True)
