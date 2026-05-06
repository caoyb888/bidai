# ============================================================
# API 集成测试：POST /api/v1/knowledge/upload
# ============================================================

import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.db import get_db
from app.main import app
from app.schemas.base import KnowledgeUploadResponse

# 使用 dependency_overrides 绕过 JWT 认证和数据库
app.dependency_overrides[get_current_user] = lambda: {
    "user_id": "test_user",
    "roles": ["BID_STAFF"],
    "permissions": ["knowledge:manage"],
}
app.dependency_overrides[get_db] = lambda: None

client = TestClient(app)


@pytest.fixture
def mock_service() -> None:
    with patch("app.api.v1.endpoints.knowledge.KnowledgeService") as MockSvc:
        instance = MockSvc.return_value
        yield instance


class TestUploadEndpoint:
    """上传接口端到端测试"""

    def test_upload_pdf_success(self, mock_service: object) -> None:
        mock_service.upload_document = AsyncMock(
            return_value=KnowledgeUploadResponse(
                task_id="task-123",
                status="PENDING",
                poll_url="/api/v1/tasks/task-123",
                estimated_seconds=30,
                document_id="doc-456",
                is_duplicate=False,
            )
        )

        response = client.post(
            "/api/v1/knowledge/upload",
            data={"doc_category": "GENERAL"},
            files={"file": ("test.pdf", io.BytesIO(b"PDF content"), "application/pdf")},
        )
        assert response.status_code == 202
        body = response.json()
        assert body["code"] == 202
        assert body["data"]["document_id"] == "doc-456"
        assert body["data"]["is_duplicate"] is False
        assert body["data"]["task_id"] == "task-123"

    def test_upload_duplicate_file(self, mock_service: object) -> None:
        mock_service.upload_document = AsyncMock(
            return_value=KnowledgeUploadResponse(
                task_id="",
                status="SUCCESS",
                poll_url="",
                estimated_seconds=0,
                document_id="doc-existing",
                is_duplicate=True,
            )
        )

        response = client.post(
            "/api/v1/knowledge/upload",
            data={"doc_category": "QUALIFICATION"},
            files={"file": ("dup.pdf", io.BytesIO(b"same"), "application/pdf")},
        )
        assert response.status_code == 202
        body = response.json()
        assert body["data"]["is_duplicate"] is True
        assert body["data"]["document_id"] == "doc-existing"

    def test_upload_invalid_type(self, mock_service: object) -> None:
        from app.core.exceptions import InvalidFileTypeError

        mock_service.upload_document = AsyncMock(side_effect=InvalidFileTypeError("exe"))

        response = client.post(
            "/api/v1/knowledge/upload",
            data={"doc_category": "GENERAL"},
            files={"file": ("virus.exe", io.BytesIO(b"exe"), "application/x-msdownload")},
        )
        assert response.status_code == 400
        body = response.json()
        assert body["code"] == 30004

    def test_upload_without_permission(self) -> None:
        # 临时覆盖依赖为无权限用户
        app.dependency_overrides[get_current_user] = lambda: {
            "user_id": "test_user",
            "roles": ["READER"],
            "permissions": ["bid:read"],
        }
        try:
            response = client.post(
                "/api/v1/knowledge/upload",
                data={"doc_category": "GENERAL"},
                files={"file": ("test.pdf", io.BytesIO(b"PDF"), "application/pdf")},
            )
            assert response.status_code == 403
            body = response.json()
            # FastAPI HTTPException detail dict is returned directly
            assert body.get("code") == 20004 or body.get("detail", {}).get("code") == 20004
        finally:
            # 恢复权限
            app.dependency_overrides[get_current_user] = lambda: {
                "user_id": "test_user",
                "roles": ["BID_STAFF"],
                "permissions": ["knowledge:manage"],
            }

    def test_upload_with_tags(self, mock_service: object) -> None:
        mock_service.upload_document = AsyncMock(
            return_value=KnowledgeUploadResponse(
                task_id="task-789",
                status="PENDING",
                poll_url="/api/v1/tasks/task-789",
                estimated_seconds=30,
                document_id="doc-abc",
                is_duplicate=False,
            )
        )

        response = client.post(
            "/api/v1/knowledge/upload",
            data={
                "doc_category": "PERFORMANCE",
                "title": "项目业绩报告",
                "tags": '["政务信息化", "广东省"]',
            },
            files={"file": ("report.pdf", io.BytesIO(b"PDF content"), "application/pdf")},
        )
        assert response.status_code == 202
        body = response.json()
        assert body["code"] == 202
        # 验证 service 被调用时 tags 已解析为列表
        call_kwargs = mock_service.upload_document.call_args.kwargs
        assert call_kwargs["tags"] == ["政务信息化", "广东省"]
