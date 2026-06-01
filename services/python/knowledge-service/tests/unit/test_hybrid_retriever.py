# ============================================================
# 单元测试：HybridRetriever
# ============================================================

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.hybrid_retriever import HybridRetriever, SearchResult


class TestHybridRetriever:
    """HybridRetriever 单元测试"""

    @pytest.fixture
    def retriever(self) -> HybridRetriever:
        """构建带 Mock 依赖的 HybridRetriever"""
        mock_embed = MagicMock()
        mock_embed.embed = AsyncMock(return_value=[[0.1] * 1536])

        mock_milvus = MagicMock()
        mock_milvus.search = MagicMock(return_value=[])

        mock_es = MagicMock()
        mock_es.search = AsyncMock(return_value=[])

        mock_reranker = MagicMock()
        mock_reranker.rerank = AsyncMock(return_value=[])

        mock_enhancer = MagicMock()
        mock_enhancer.enhance = AsyncMock(return_value="增强后的查询")

        return HybridRetriever(
            query_enhancer=mock_enhancer,
            embed_client=mock_embed,
            milvus_client=mock_milvus,
            es_client=mock_es,
            reranker=mock_reranker,
        )

    async def test_retrieve_empty_results(self, retriever: HybridRetriever) -> None:
        """测试无结果场景"""
        results = await retriever.retrieve("查询", top_k=5)
        assert results == []

    async def test_retrieve_success_flow(self, retriever: HybridRetriever) -> None:
        """测试正常检索流程"""
        retriever.milvus.search = MagicMock(
            return_value=[
                {"chunk_id": "c1", "doc_id": "d1", "score": 0.9, "chunk_type": "TEXT"},
            ]
        )
        retriever.es.search = AsyncMock(
            return_value=[
                {
                    "chunk_id": "c2",
                    "doc_id": "d1",
                    "content": "ES内容",
                    "score": 1.2,
                    "doc_title": "标题",
                    "highlight": "<em>高亮</em>",
                }
            ]
        )
        retriever.reranker.rerank = AsyncMock(
            return_value=[
                MagicMock(chunk_id="c2", score=0.95),
                MagicMock(chunk_id="c1", score=0.85),
            ]
        )

        results = await retriever.retrieve("查询", top_k=2)

        assert len(results) == 2
        assert results[0].chunk_id == "c2"
        assert results[0].score == 0.95
        assert results[0].content == "ES内容"
        assert results[1].chunk_id == "c1"

    async def test_retrieve_vector_only_fallback(self, retriever: HybridRetriever) -> None:
        """测试 ES 失败时仅向量检索仍可工作"""
        retriever.milvus.search = MagicMock(
            return_value=[
                {"chunk_id": "c1", "doc_id": "d1", "score": 0.9, "chunk_type": "TEXT"},
            ]
        )
        retriever.es.search = AsyncMock(side_effect=Exception("ES down"))
        retriever.reranker.rerank = AsyncMock(
            return_value=[MagicMock(chunk_id="c1", score=0.9)]
        )

        results = await retriever.retrieve("查询", top_k=1)

        assert len(results) == 1
        assert results[0].chunk_id == "c1"

    async def test_merge_and_deduplicate(self, retriever: HybridRetriever) -> None:
        """测试结果融合去重"""
        vector_results = [
            SearchResult("c1", "d1", "", "", None, 0.9, "", "vector"),
            SearchResult("c2", "d1", "", "", None, 0.8, "", "vector"),
        ]
        fulltext_results = [
            SearchResult("c1", "d1", "标题", "内容", 1, 1.2, "高亮", "fulltext"),
            SearchResult("c3", "d1", "", "", None, 0.7, "", "fulltext"),
        ]

        merged = retriever._merge_and_deduplicate(vector_results, fulltext_results)

        assert len(merged) == 3
        # c1 应该被融合，source 变为 hybrid，content 和 highlight 被补充
        c1 = next(m for m in merged if m.chunk_id == "c1")
        assert c1.source == "hybrid"
        assert c1.content == "内容"
        assert c1.highlight == "高亮"
        assert c1.score == 1.2  # 取更高分
