# ============================================================
# 单元测试：知识库文档列表/详情/删除 API
# ============================================================

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _mock_current_user_bid_edit() -> dict[str, str | list[str]]:
    return {"user_id": "u1", "permissions": ["bid:edit"]}


def _mock_current_user_manage() -> dict[str, str | list[str]]:
    return {"user_id": "u1", "permissions": ["bid:edit", "knowledge:manage"]}


def _mock_current_user_no_permission() -> dict[str, str | list[str]]:
    return {"user_id": "u1", "permissions": []}


class TestListDocumentsAPI:
    """GET /knowledge/documents 接口测试"""

    @pytest.fixture(autouse=True)
    def setup_override(self) -> None:
        from app.api.v1.endpoints.knowledge import get_current_user

        app.dependency_overrides[get_current_user] = _mock_current_user_bid_edit
        yield
        app.dependency_overrides.clear()

    @patch("app.api.v1.endpoints.knowledge.KnowledgeService.list_documents")
    async def test_list_documents_success(self, mock_list: AsyncMock) -> None:
        """测试正常列表查询返回 200"""
        mock_list.return_value = MagicMock(
            items=[
                MagicMock(
                    id="doc-1",
                    title="测试文档",
                    doc_category="GENERAL",
                    tags=["标签1"],
                    file_type="pdf",
                    page_count=10,
                    confidence=0.95,
                    ingest_mode="AUTO",
                    is_expired=False,
                    created_at="2026-01-01T00:00:00Z",
                )
            ],
            total=1,
            page=1,
            page_size=20,
            total_pages=1,
        )

        response = client.get("/api/v1/knowledge/documents")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["total"] == 1
        assert len(data["data"]["items"]) == 1
        assert data["data"]["items"][0]["id"] == "doc-1"

    @patch("app.api.v1.endpoints.knowledge.KnowledgeService.list_documents")
    async def test_list_documents_with_filters(self, mock_list: AsyncMock) -> None:
        """测试带筛选条件的列表查询"""
        mock_list.return_value = MagicMock(
            items=[], total=0, page=1, page_size=20, total_pages=0
        )

        response = client.get(
            "/api/v1/knowledge/documents?doc_category=QUALIFICATION&is_expired=false&keyword=测试"
        )

        assert response.status_code == 200
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs["doc_category"] == "QUALIFICATION"
        assert call_kwargs["is_expired"] is False
        assert call_kwargs["keyword"] == "测试"

    async def test_list_documents_without_permission(self) -> None:
        """测试无权限返回 403"""
        from app.api.v1.endpoints.knowledge import get_current_user

        app.dependency_overrides[get_current_user] = _mock_current_user_no_permission

        response = client.get("/api/v1/knowledge/documents")
        assert response.status_code == 403
        assert response.json()["code"] == 20004

        app.dependency_overrides.clear()


class TestGetDocumentAPI:
    """GET /knowledge/documents/{id} 接口测试"""

    @pytest.fixture(autouse=True)
    def setup_override(self) -> None:
        from app.api.v1.endpoints.knowledge import get_current_user

        app.dependency_overrides[get_current_user] = _mock_current_user_bid_edit
        yield
        app.dependency_overrides.clear()

    @patch("app.api.v1.endpoints.knowledge.KnowledgeService.get_document")
    async def test_get_document_success(self, mock_get: AsyncMock) -> None:
        """测试正常详情查询返回 200"""
        mock_get.return_value = MagicMock(
            id="doc-1",
            title="测试文档",
            doc_category="GENERAL",
            tags=["标签1"],
            file_type="pdf",
            page_count=10,
            confidence=0.95,
            ingest_mode="AUTO",
            is_expired=False,
            created_at="2026-01-01T00:00:00Z",
        )

        response = client.get("/api/v1/knowledge/documents/doc-1")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["id"] == "doc-1"
        assert data["data"]["title"] == "测试文档"

    @patch("app.api.v1.endpoints.knowledge.KnowledgeService.get_document")
    async def test_get_document_not_found(self, mock_get: AsyncMock) -> None:
        """测试文档不存在返回 404"""
        from app.core.exceptions import NotFoundError

        mock_get.side_effect = NotFoundError("知识库文档")

        response = client.get("/api/v1/knowledge/documents/non-existent")

        assert response.status_code == 404
        assert response.json()["code"] == 40002


class TestDeleteDocumentAPI:
    """DELETE /knowledge/documents/{id} 接口测试"""

    @pytest.fixture(autouse=True)
    def setup_override(self) -> None:
        from app.api.v1.endpoints.knowledge import get_current_user

        app.dependency_overrides[get_current_user] = _mock_current_user_manage
        yield
        app.dependency_overrides.clear()

    @patch("app.api.v1.endpoints.knowledge.KnowledgeService.delete_document")
    async def test_delete_document_success(self, mock_delete: AsyncMock) -> None:
        """测试正常删除返回 204"""
        response = client.delete("/api/v1/knowledge/documents/doc-1")

        assert response.status_code == 204
        mock_delete.assert_called_once_with("doc-1", "u1")

    @patch("app.api.v1.endpoints.knowledge.KnowledgeService.delete_document")
    async def test_delete_document_not_found(self, mock_delete: AsyncMock) -> None:
        """测试删除不存在的文档返回 404"""
        from app.core.exceptions import NotFoundError

        mock_delete.side_effect = NotFoundError("知识库文档")

        response = client.delete("/api/v1/knowledge/documents/non-existent")

        assert response.status_code == 404
        assert response.json()["code"] == 40002

    async def test_delete_document_without_manage_permission(self) -> None:
        """测试无 manage 权限返回 403"""
        from app.api.v1.endpoints.knowledge import get_current_user

        app.dependency_overrides[get_current_user] = _mock_current_user_bid_edit

        response = client.delete("/api/v1/knowledge/documents/doc-1")
        assert response.status_code == 403
        assert response.json()["code"] == 20004

        app.dependency_overrides.clear()
