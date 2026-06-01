# ============================================================
# 单元测试：GET /knowledge/stats API（S1-2-006）
# ============================================================

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _mock_current_user_bid_edit() -> dict[str, str | list[str]]:
    return {"user_id": "u1", "permissions": ["bid:edit"]}


def _mock_current_user_no_permission() -> dict[str, str | list[str]]:
    return {"user_id": "u1", "permissions": []}


class TestGetKnowledgeStatsAPI:
    """GET /knowledge/stats 接口测试"""

    @pytest.fixture(autouse=True)
    def setup_override(self) -> None:
        from app.api.v1.endpoints.knowledge import get_current_user

        app.dependency_overrides[get_current_user] = _mock_current_user_bid_edit
        yield
        app.dependency_overrides.clear()

    @patch("app.api.v1.endpoints.knowledge.KnowledgeService.get_stats")
    async def test_get_stats_success(self, mock_stats: AsyncMock) -> None:
        """测试正常获取统计信息返回 200"""
        mock_stats.return_value = MagicMock(
            total_documents=100,
            health_score=85.5,
            category_stats=[
                MagicMock(category="QUALIFICATION", count=20, expired_count=1),
                MagicMock(category="PERFORMANCE", count=30, expired_count=0),
                MagicMock(category="PERSONNEL", count=10, expired_count=0),
                MagicMock(category="SOLUTION_TEMPLATE", count=25, expired_count=2),
                MagicMock(category="GENERAL", count=15, expired_count=0),
            ],
            expiring_soon=[
                MagicMock(doc_id="doc-1", title="证书A", expire_date="2026-07-15"),
            ],
        )

        response = client.get("/api/v1/knowledge/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["total_documents"] == 100
        assert data["data"]["health_score"] == 85.5
        assert len(data["data"]["category_stats"]) == 5
        assert len(data["data"]["expiring_soon"]) == 1
        assert data["data"]["expiring_soon"][0]["doc_id"] == "doc-1"

    @patch("app.api.v1.endpoints.knowledge.KnowledgeService.get_stats")
    async def test_get_stats_empty(self, mock_stats: AsyncMock) -> None:
        """测试空知识库统计返回 200"""
        mock_stats.return_value = MagicMock(
            total_documents=0,
            health_score=0.0,
            category_stats=[
                MagicMock(category="QUALIFICATION", count=0, expired_count=0),
                MagicMock(category="PERFORMANCE", count=0, expired_count=0),
                MagicMock(category="PERSONNEL", count=0, expired_count=0),
                MagicMock(category="SOLUTION_TEMPLATE", count=0, expired_count=0),
                MagicMock(category="GENERAL", count=0, expired_count=0),
            ],
            expiring_soon=[],
        )

        response = client.get("/api/v1/knowledge/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total_documents"] == 0
        assert data["data"]["health_score"] == 0.0
        assert data["data"]["expiring_soon"] == []

    async def test_get_stats_without_permission(self) -> None:
        """测试无权限返回 403"""
        from app.api.v1.endpoints.knowledge import get_current_user

        app.dependency_overrides[get_current_user] = _mock_current_user_no_permission

        response = client.get("/api/v1/knowledge/stats")
        assert response.status_code == 403
        assert response.json()["code"] == 20004

        app.dependency_overrides.clear()
