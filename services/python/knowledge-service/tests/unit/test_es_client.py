# ============================================================
# 单元测试：Elasticsearch 客户端
# ============================================================

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.es_client import ESClient, ESError


@pytest.fixture(autouse=True)
def reset_es_singleton():
    """每次测试前重置 ESClient 单例"""
    ESClient._instance = None
    ESClient._client = None
    yield
    ESClient._instance = None
    ESClient._client = None


class TestESClient:
    """ESClient 单元测试"""

    @patch("app.ai.es_client.AsyncElasticsearch")
    async def test_ensure_index_creates_when_missing(self, mock_es_cls: MagicMock) -> None:
        """测试索引不存在时自动创建"""
        mock_client = AsyncMock()
        mock_client.indices.exists.return_value = False
        mock_es_cls.return_value = mock_client

        es = ESClient()
        await es.ensure_index()

        mock_client.indices.create.assert_called_once()
        call_args = mock_client.indices.create.call_args.kwargs
        assert call_args["index"] == "kb_chunks"
        assert "mappings" in call_args["body"]

    @patch("app.ai.es_client.AsyncElasticsearch")
    async def test_ensure_index_skips_when_exists(self, mock_es_cls: MagicMock) -> None:
        """测试索引已存在时不重复创建"""
        mock_client = AsyncMock()
        mock_client.indices.exists.return_value = True
        mock_es_cls.return_value = mock_client

        es = ESClient()
        await es.ensure_index()

        mock_client.indices.create.assert_not_called()

    @patch("app.ai.es_client.AsyncElasticsearch")
    async def test_search_returns_hits(self, mock_es_cls: MagicMock) -> None:
        """测试全文搜索返回正确格式"""
        mock_client = AsyncMock()
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "chunk_id": "c1",
                            "doc_id": "d1",
                            "content": "测试内容",
                            "chunk_type": "TEXT",
                            "page_no": 1,
                            "section_title": "",
                            "doc_title": "文档标题",
                        },
                        "_score": 1.5,
                        "highlight": {"content": ["<em>测试</em>内容"]},
                    }
                ]
            }
        }
        mock_es_cls.return_value = mock_client

        es = ESClient()
        hits = await es.search(query="测试", top_k=10)

        assert len(hits) == 1
        assert hits[0]["chunk_id"] == "c1"
        assert hits[0]["content"] == "测试内容"
        assert hits[0]["doc_title"] == "文档标题"
        assert hits[0]["score"] == 1.5

    @patch("app.ai.es_client.AsyncElasticsearch")
    async def test_delete_by_doc_id(self, mock_es_cls: MagicMock) -> None:
        """测试按 doc_id 删除"""
        mock_client = AsyncMock()
        mock_client.delete_by_query.return_value = {"deleted": 3}
        mock_es_cls.return_value = mock_client

        es = ESClient()
        deleted = await es.delete_by_doc_id("doc123")

        assert deleted == 3

    @patch("app.ai.es_client.AsyncElasticsearch")
    async def test_bulk_index_chunks(self, mock_es_cls: MagicMock) -> None:
        """测试批量索引"""
        mock_client = AsyncMock()
        mock_es_cls.return_value = mock_client

        with patch("app.ai.es_client.async_bulk") as mock_bulk:
            mock_bulk.return_value = (2, [])
            es = ESClient()
            await es.bulk_index_chunks(
                [
                    {"chunk_id": "c1", "doc_id": "d1", "content": "内容1"},
                    {"chunk_id": "c2", "doc_id": "d1", "content": "内容2"},
                ]
            )
            mock_bulk.assert_called_once()
