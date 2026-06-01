# ============================================================
# 单元测试：知识库搜索 API
# ============================================================

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _mock_current_user() -> dict[str, str | list[str]]:
    return {"user_id": "u1", "permissions": ["bid:edit"]}


class TestSearchAPI:
    """GET /knowledge/search 接口测试"""

    @pytest.fixture(autouse=True)
    def setup_override(self) -> None:
        """覆盖当前用户依赖"""
        from app.api.v1.endpoints.knowledge import get_current_user
        app.dependency_overrides[get_current_user] = _mock_current_user
        yield
        app.dependency_overrides.clear()

    @patch("app.api.v1.endpoints.knowledge.KnowledgeService.search_knowledge")
    async def test_search_success(self, mock_search: AsyncMock) -> None:
        """测试正常搜索返回 200"""
        mock_search.return_value = MagicMock(
            results=[
                MagicMock(
                    chunk_id="c1",
                    doc_id="d1",
                    doc_title="测试文档",
                    content="测试内容",
                    page_no=1,
                    score=0.95,
                    highlight="<em>测试</em>内容",
                )
            ],
            total_found=1,
        )

        response = client.get("/api/v1/knowledge/search?query=测试&top_k=5")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["total_found"] == 1
        assert len(data["data"]["results"]) == 1
        assert data["data"]["results"][0]["chunk_id"] == "c1"

    async def test_search_missing_query(self) -> None:
        """测试缺少 query 参数返回 422"""
        response = client.get("/api/v1/knowledge/search")
        assert response.status_code == 422

    async def test_search_query_too_short(self) -> None:
        """测试 query 太短返回 422"""
        response = client.get("/api/v1/knowledge/search?query=a")
        assert response.status_code == 422

    @patch("app.api.v1.endpoints.knowledge.KnowledgeService.search_knowledge")
    async def test_search_with_filters(self, mock_search: AsyncMock) -> None:
        """测试带过滤条件的搜索"""
        mock_search.return_value = MagicMock(results=[], total_found=0)

        response = client.get(
            "/api/v1/knowledge/search?query=投标方案&doc_category=QUALIFICATION&top_k=20"
        )

        assert response.status_code == 200
        mock_search.assert_called_once()
        call_args = mock_search.call_args.args[0]
        assert call_args.query == "投标方案"
        assert call_args.doc_category == "QUALIFICATION"
        assert call_args.top_k == 20
