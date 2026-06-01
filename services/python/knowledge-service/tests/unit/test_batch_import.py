# ============================================================
# 批量导入工具单元测试
# ============================================================

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.cli.batch_import import (
    ImportFileItem,
    ImportReport,
    generate_report,
    infer_category,
    scan_source_dir,
    upload_single,
)


class TestInferCategory:
    """测试分类推断"""

    @pytest.mark.parametrize(
        ("dir_name", "expected"),
        [
            ("qualification", "QUALIFICATION"),
            ("QUALIFICATION", "QUALIFICATION"),
            ("Qualifications", "QUALIFICATION"),
            ("performance", "PERFORMANCE"),
            ("performances", "PERFORMANCE"),
            ("case", "PERFORMANCE"),
            ("cases", "PERFORMANCE"),
            ("personnel", "PERSONNEL"),
            ("people", "PERSONNEL"),
            ("staff", "PERSONNEL"),
            ("solution", "SOLUTION_TEMPLATE"),
            ("solutions", "SOLUTION_TEMPLATE"),
            ("template", "SOLUTION_TEMPLATE"),
            ("templates", "SOLUTION_TEMPLATE"),
            ("general", "GENERAL"),
            ("misc", "GENERAL"),
            ("others", "GENERAL"),
            ("unknown", "GENERAL"),
            ("", "GENERAL"),
        ],
    )
    def test_infer_category(self, dir_name: str, expected: str) -> None:
        assert infer_category(dir_name) == expected


class TestScanSourceDir:
    """测试目录扫描"""

    def test_scan_empty_dir(self, tmp_path: Path) -> None:
        items = scan_source_dir(tmp_path)
        assert items == []

    def test_scan_skips_hidden_files(self, tmp_path: Path) -> None:
        qual_dir = tmp_path / "qualification"
        qual_dir.mkdir()
        (qual_dir / "doc.pdf").write_text("pdf")
        (qual_dir / ".hidden.pdf").write_text("hidden")

        items = scan_source_dir(tmp_path)
        assert len(items) == 1
        assert items[0].relative_path == "qualification/doc.pdf"

    def test_scan_skips_unsupported_extensions(self, tmp_path: Path) -> None:
        qual_dir = tmp_path / "qualification"
        qual_dir.mkdir()
        (qual_dir / "doc.pdf").write_text("pdf")
        (qual_dir / "doc.exe").write_text("exe")

        items = scan_source_dir(tmp_path)
        assert len(items) == 1
        assert items[0].file_path.name == "doc.pdf"

    def test_scan_maps_categories(self, tmp_path: Path) -> None:
        (tmp_path / "qualification").mkdir()
        (tmp_path / "performance").mkdir()
        (tmp_path / "personnel").mkdir()
        (tmp_path / "solution").mkdir()
        (tmp_path / "general").mkdir()

        (tmp_path / "qualification" / "q.pdf").write_text("q")
        (tmp_path / "performance" / "p.pdf").write_text("p")
        (tmp_path / "personnel" / "pe.pdf").write_text("pe")
        (tmp_path / "solution" / "s.pdf").write_text("s")
        (tmp_path / "general" / "g.pdf").write_text("g")

        items = scan_source_dir(tmp_path)
        assert len(items) == 5

        categories = {item.doc_category for item in items}
        assert categories == {
            "QUALIFICATION",
            "PERFORMANCE",
            "PERSONNEL",
            "SOLUTION_TEMPLATE",
            "GENERAL",
        }

    def test_scan_nonexistent_dir(self, tmp_path: Path) -> None:
        items = scan_source_dir(tmp_path / "does_not_exist")
        assert items == []

    def test_scan_only_first_level_subdirs(self, tmp_path: Path) -> None:
        qual_dir = tmp_path / "qualification"
        qual_dir.mkdir()
        nested = qual_dir / "nested"
        nested.mkdir()
        (nested / "doc.pdf").write_text("pdf")

        items = scan_source_dir(tmp_path)
        assert len(items) == 0


class TestUploadSingle:
    """测试单文件上传（Mock Service 层）"""

    @pytest.mark.asyncio
    async def test_upload_success(self, tmp_path: Path) -> None:
        item = ImportFileItem(
            file_path=tmp_path / "test.pdf",
            doc_category="QUALIFICATION",
            relative_path="qualification/test.pdf",
        )
        item.file_path.write_text("pdf content")

        mock_result = MagicMock()
        mock_result.document_id = "doc-123"
        mock_result.is_duplicate = False

        with patch(
            "app.cli.batch_import.KnowledgeService"
        ) as MockService:
            instance = MockService.return_value
            instance.upload_document = AsyncMock(return_value=mock_result)

            await upload_single(item, user_id="system/test")

            assert item.status == "SUCCESS"
            assert item.document_id == "doc-123"
            assert item.is_duplicate is False
            assert item.duration_ms > 0
            instance.upload_document.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_upload_duplicate(self, tmp_path: Path) -> None:
        item = ImportFileItem(
            file_path=tmp_path / "test.pdf",
            doc_category="QUALIFICATION",
            relative_path="qualification/test.pdf",
        )
        item.file_path.write_text("pdf content")

        mock_result = MagicMock()
        mock_result.document_id = "doc-old"
        mock_result.is_duplicate = True

        with patch(
            "app.cli.batch_import.KnowledgeService"
        ) as MockService:
            instance = MockService.return_value
            instance.upload_document = AsyncMock(return_value=mock_result)

            await upload_single(item, user_id="system/test")

            assert item.status == "DUPLICATE"
            assert item.document_id == "doc-old"

    @pytest.mark.asyncio
    async def test_upload_invalid_file_type(self, tmp_path: Path) -> None:
        item = ImportFileItem(
            file_path=tmp_path / "test.pdf",
            doc_category="QUALIFICATION",
            relative_path="qualification/test.pdf",
        )
        item.file_path.write_text("pdf content")

        from app.core.exceptions import InvalidFileTypeError

        with patch(
            "app.cli.batch_import.KnowledgeService"
        ) as MockService:
            instance = MockService.return_value
            instance.upload_document = AsyncMock(
                side_effect=InvalidFileTypeError("xyz")
            )

            await upload_single(item, user_id="system/test")

            assert item.status == "FAILED"
            assert "不支持的文件类型" in (item.error_message or "")

    @pytest.mark.asyncio
    async def test_upload_storage_error(self, tmp_path: Path) -> None:
        item = ImportFileItem(
            file_path=tmp_path / "test.pdf",
            doc_category="QUALIFICATION",
            relative_path="qualification/test.pdf",
        )
        item.file_path.write_text("pdf content")

        from app.core.exceptions import StorageError

        with patch(
            "app.cli.batch_import.KnowledgeService"
        ) as MockService:
            instance = MockService.return_value
            instance.upload_document = AsyncMock(
                side_effect=StorageError("minio down")
            )

            await upload_single(item, user_id="system/test")

            assert item.status == "FAILED"
            assert "存储失败" in (item.error_message or "")

    @pytest.mark.asyncio
    async def test_upload_unexpected_error(self, tmp_path: Path) -> None:
        item = ImportFileItem(
            file_path=tmp_path / "test.pdf",
            doc_category="QUALIFICATION",
            relative_path="qualification/test.pdf",
        )
        item.file_path.write_text("pdf content")

        with patch(
            "app.cli.batch_import.KnowledgeService"
        ) as MockService:
            instance = MockService.return_value
            instance.upload_document = AsyncMock(side_effect=RuntimeError("boom"))

            await upload_single(item, user_id="system/test")

            assert item.status == "FAILED"
            assert "上传异常" in (item.error_message or "")


class TestGenerateReport:
    """测试报告生成"""

    def test_report_counts(self) -> None:
        items = [
            ImportFileItem(
                file_path=Path("/a.pdf"),
                doc_category="QUALIFICATION",
                relative_path="a.pdf",
                status="SUCCESS",
            ),
            ImportFileItem(
                file_path=Path("/b.pdf"),
                doc_category="PERFORMANCE",
                relative_path="b.pdf",
                status="DUPLICATE",
            ),
            ImportFileItem(
                file_path=Path("/c.pdf"),
                doc_category="PERSONNEL",
                relative_path="c.pdf",
                status="FAILED",
                error_message="err",
            ),
            ImportFileItem(
                file_path=Path("/d.pdf"),
                doc_category="GENERAL",
                relative_path="d.pdf",
                status="PENDING",
            ),
        ]

        report = generate_report(
            items,
            started_at="2026-06-01T10:00:00",
            source_dir=Path("/data"),
            total_duration_ms=1234.5,
        )

        assert report.total_files == 4
        assert report.success_count == 1
        assert report.duplicate_count == 1
        assert report.failed_count == 1
        assert report.skipped_count == 1
        assert report.source_dir == "/data"
        assert len(report.files) == 4

    def test_report_json_output(self) -> None:
        items = [
            ImportFileItem(
                file_path=Path("/a.pdf"),
                doc_category="QUALIFICATION",
                relative_path="a.pdf",
                status="SUCCESS",
                document_id="doc-1",
            ),
        ]

        report = generate_report(
            items,
            started_at="2026-06-01T10:00:00",
            source_dir=Path("/data"),
            total_duration_ms=100.0,
        )

        json_str = report.to_json()
        assert '"total_files": 1' in json_str
        assert '"success_count": 1' in json_str
