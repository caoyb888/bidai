# ============================================================
# 单元测试：KnowledgeService.upload_document
# ============================================================

import io
from typing import BinaryIO
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.exceptions import (
    FileTooLargeError,
    InvalidFileTypeError,
)
from app.models.kb_document import KbDocument
from app.schemas.base import KnowledgeUploadResponse
from app.services.knowledge import KnowledgeService


@pytest.fixture
def mock_session() -> MagicMock:
    """Mock AsyncSession"""
    session = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def service(mock_session: MagicMock) -> KnowledgeService:
    svc = KnowledgeService(mock_session)
    # mock repositories with AsyncMock for async methods
    svc.kb_repo = MagicMock()
    svc.kb_repo.get_by_file_hash = AsyncMock()
    svc.kb_repo.create = AsyncMock()
    svc.task_repo = MagicMock()
    svc.task_repo.create = AsyncMock()
    svc.minio = MagicMock()
    return svc


def _make_file(content: bytes, name: str = "test.pdf") -> BinaryIO:
    return io.BytesIO(content)


class TestFileTypeValidation:
    """文件类型白名单校验测试"""

    @pytest.mark.asyncio
    async def test_valid_pdf(self, service: KnowledgeService) -> None:
        file = _make_file(b"PDF content", "document.pdf")
        service.kb_repo.get_by_file_hash.return_value = None
        service.minio.upload_file.return_value = "path/to/file"
        service.task_repo.create.return_value = MagicMock(id=uuid4())

        with patch("app.services.knowledge.process_document_task") as mock_process:
            mock_process.delay = MagicMock(return_value=MagicMock(id="celery-task-id"))
            result = await service.upload_document(
                file_data=file,
                file_name="document.pdf",
                mime_type="application/pdf",
                doc_category="GENERAL",
                title=None,
                tags=[],
                user_id="user_001",
            )
            assert isinstance(result, KnowledgeUploadResponse)
            assert result.is_duplicate is False

    @pytest.mark.asyncio
    async def test_invalid_file_type(self, service: KnowledgeService) -> None:
        file = _make_file(b"exe content", "virus.exe")

        with pytest.raises(InvalidFileTypeError) as exc_info:
            await service.upload_document(
                file_data=file,
                file_name="virus.exe",
                mime_type="application/x-msdownload",
                doc_category="GENERAL",
                title=None,
                tags=[],
                user_id="user_001",
            )
        assert exc_info.value.biz_code == 30004

    @pytest.mark.asyncio
    async def test_valid_docx(self, service: KnowledgeService) -> None:
        file = _make_file(b"DOCX content", "report.docx")
        service.kb_repo.get_by_file_hash.return_value = None
        service.minio.upload_file.return_value = "path/to/file"
        service.task_repo.create.return_value = MagicMock(id=uuid4())

        with patch("app.services.knowledge.process_document_task") as mock_process:
            mock_process.delay = MagicMock(return_value=MagicMock(id="celery-task-id"))
            result = await service.upload_document(
                file_data=file,
                file_name="report.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                doc_category="GENERAL",
                title=None,
                tags=[],
                user_id="user_001",
            )
            assert result.is_duplicate is False


class TestFileSizeValidation:
    """文件大小限制校验测试"""

    @pytest.mark.asyncio
    async def test_file_within_limit(self, service: KnowledgeService) -> None:
        content = b"x" * (10 * 1024 * 1024)  # 10 MB
        file = _make_file(content, "medium.pdf")
        service.kb_repo.get_by_file_hash.return_value = None
        service.minio.upload_file.return_value = "path/to/file"
        service.task_repo.create.return_value = MagicMock(id=uuid4())

        with patch("app.services.knowledge.process_document_task") as mock_process:
            mock_process.delay = MagicMock(return_value=MagicMock(id="celery-task-id"))
            result = await service.upload_document(
                file_data=file,
                file_name="medium.pdf",
                mime_type="application/pdf",
                doc_category="GENERAL",
                title=None,
                tags=[],
                user_id="user_001",
            )
            assert result.is_duplicate is False

    @pytest.mark.asyncio
    async def test_file_exceeds_limit(self, service: KnowledgeService) -> None:
        content = b"x" * ((settings.upload_max_size_mb + 1) * 1024 * 1024)
        file = _make_file(content, "huge.pdf")

        with pytest.raises(FileTooLargeError) as exc_info:
            await service.upload_document(
                file_data=file,
                file_name="huge.pdf",
                mime_type="application/pdf",
                doc_category="GENERAL",
                title=None,
                tags=[],
                user_id="user_001",
            )
        assert exc_info.value.biz_code == 30005


class TestDuplicateDetection:
    """SHA-256 去重测试"""

    @pytest.mark.asyncio
    async def test_duplicate_file_returns_existing(self, service: KnowledgeService) -> None:
        existing_doc = KbDocument(
            id=uuid4(),
            doc_type="MISC",
            title="Existing",
            file_path="path",
            file_name="existing.pdf",
            file_size_bytes=100,
            mime_type="application/pdf",
            file_hash="abc123",
        )
        service.kb_repo.get_by_file_hash.return_value = existing_doc

        file = _make_file(b"same content", "duplicate.pdf")
        result = await service.upload_document(
            file_data=file,
            file_name="duplicate.pdf",
            mime_type="application/pdf",
            doc_category="GENERAL",
            title=None,
            tags=[],
            user_id="user_001",
        )
        assert result.is_duplicate is True
        assert result.document_id == str(existing_doc.id)

    @pytest.mark.asyncio
    async def test_new_file_proceeds(self, service: KnowledgeService) -> None:
        service.kb_repo.get_by_file_hash.return_value = None
        service.minio.upload_file.return_value = "path/to/file"
        service.task_repo.create.return_value = MagicMock(id=uuid4())

        file = _make_file(b"unique content", "new.pdf")
        with patch("app.services.knowledge.process_document_task") as mock_process:
            mock_process.delay = MagicMock(return_value=MagicMock(id="celery-task-id"))
            result = await service.upload_document(
                file_data=file,
                file_name="new.pdf",
                mime_type="application/pdf",
                doc_category="GENERAL",
                title=None,
                tags=[],
                user_id="user_001",
            )
            assert result.is_duplicate is False
            assert result.task_id != ""


class TestDocCategoryMapping:
    """文档分类映射测试"""

    def test_solution_template_maps_to_solution(self) -> None:
        assert KnowledgeService._map_doc_category("SOLUTION_TEMPLATE") == "SOLUTION"

    def test_general_maps_to_misc(self) -> None:
        assert KnowledgeService._map_doc_category("GENERAL") == "MISC"

    def test_qualification_unchanged(self) -> None:
        assert KnowledgeService._map_doc_category("QUALIFICATION") == "QUALIFICATION"
