# ============================================================
# 单元测试：Cross-Encoder Reranker
# ============================================================

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.reranker import RerankerClient, RerankerError


class TestRerankerClient:
    """RerankerClient 单元测试"""

    @patch("app.ai.reranker.settings")
    @pytest.mark.asyncio
    async def test_not_configured_returns_original_order(self, mock_settings: MagicMock) -> None:
        """测试未配置时返回原始顺序"""
        mock_settings.reranker_api_url = ""
        client = RerankerClient()

        candidates = [
            {"chunk_id": "c1", "content": "内容1", "score": 0.8},
            {"chunk_id": "c2", "content": "内容2", "score": 0.6},
        ]

        results = await client.rerank("查询", candidates)

        assert len(results) == 2
        assert results[0].chunk_id == "c1"
        assert results[1].chunk_id == "c2"

    @patch("app.ai.reranker.settings")
    @patch("app.ai.reranker.httpx.AsyncClient")
    async def test_rerank_success(self, mock_http_cls: MagicMock, mock_settings: MagicMock) -> None:
        """测试正常重排序流程"""
        mock_settings.reranker_api_url = "http://reranker.local/rerank"
        mock_settings.reranker_api_key = "test-key"
        mock_settings.reranker_model = "rerank-model"
        mock_settings.reranker_timeout = 10

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"index": 1, "relevance_score": 0.95},
                {"index": 0, "relevance_score": 0.85},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_http = MagicMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http_cls.return_value = mock_http

        client = RerankerClient()
        candidates = [
            {"chunk_id": "c1", "content": "内容1"},
            {"chunk_id": "c2", "content": "内容2"},
        ]

        results = await client.rerank("查询", candidates, top_k=2)

        assert len(results) == 2
        assert results[0].chunk_id == "c2"  # score 0.95 排第一
        assert results[1].chunk_id == "c1"  # score 0.85 排第二
        assert results[0].score == 0.95

    @patch("app.ai.reranker.settings")
    @patch("app.ai.reranker.httpx.AsyncClient")
    async def test_rerank_api_error(self, mock_http_cls: MagicMock, mock_settings: MagicMock) -> None:
        """测试 API 错误时抛出异常"""
        mock_settings.reranker_api_url = "http://reranker.local/rerank"
        mock_settings.reranker_api_key = ""
        mock_settings.reranker_model = ""
        mock_settings.reranker_timeout = 10

        mock_http = MagicMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        import httpx

        mock_http.post = AsyncMock(side_effect=httpx.RequestError("connection error"))
        mock_http_cls.return_value = mock_http

        client = RerankerClient()
        with pytest.raises(RerankerError):
            await client.rerank("查询", [{"chunk_id": "c1", "content": "内容"}])
