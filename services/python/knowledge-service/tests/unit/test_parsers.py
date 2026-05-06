# ============================================================
# 单元测试：OCR 解析器
# ============================================================

from unittest.mock import MagicMock, patch

import pytest

from app.ai.parsers.base import count_words
from app.ai.parsers.docx_parser import DocxParser
from app.ai.parsers.factory import UnsupportedFileTypeError, get_parser
from app.ai.parsers.image_parser import ImageParser
from app.ai.parsers.pdf_parser import PdfParser


class TestCountWords:
    """字数统计测试"""

    def test_chinese_only(self) -> None:
        assert count_words("这是一段中文文本") == 8

    def test_english_only(self) -> None:
        assert count_words("Hello world test") == 3

    def test_mixed(self) -> None:
        assert count_words("Hello 世界 this 是 test") == 6

    def test_empty(self) -> None:
        assert count_words("") == 0


class TestFactory:
    """解析器工厂测试"""

    def test_pdf_parser(self) -> None:
        parser = get_parser("application/pdf")
        assert isinstance(parser, PdfParser)

    def test_docx_parser(self) -> None:
        parser = get_parser("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        assert isinstance(parser, DocxParser)

    def test_jpeg_parser(self) -> None:
        parser = get_parser("image/jpeg")
        assert isinstance(parser, ImageParser)

    def test_png_parser(self) -> None:
        parser = get_parser("image/png")
        assert isinstance(parser, ImageParser)

    def test_unsupported_type(self) -> None:
        with pytest.raises(UnsupportedFileTypeError) as exc_info:
            get_parser("application/zip")
        assert exc_info.value.biz_code == 30004


class TestPdfParser:
    """PDF 解析器测试"""

    @patch("app.ai.parsers.pdf_parser.fitz.open")
    def test_digital_text_pdf(self, mock_fitz_open: MagicMock) -> None:
        """测试数字文本 PDF 解析（无需 OCR）"""
        # Mock 文档
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=2)

        # Mock 第1页（数字文本页）
        mock_page1 = MagicMock()
        mock_page1.number = 0
        mock_page1.get_text.return_value = (
            "第一章 项目概述\n\n"
            "本项目旨在建设智慧城市平台，通过大数据、人工智能等先进技术，"
            "实现城市管理的智能化和精细化。项目涵盖智慧交通、智慧环保、智慧安防等多个领域。"
        )
        mock_page1.get_pixmap = MagicMock()

        # Mock 第2页（数字文本页）
        mock_page2 = MagicMock()
        mock_page2.number = 1
        mock_page2.get_text.return_value = (
            "第二章 技术方案\n\n"
            "采用微服务架构设计，基于容器化部署方案，使用 Kubernetes 进行 orchestration。"
            "系统包含多个独立部署的服务模块，通过 RESTful API 进行通信。"
        )
        mock_page2.get_pixmap = MagicMock()

        def load_page(idx: int) -> MagicMock:
            return [mock_page1, mock_page2][idx]

        mock_doc.load_page = load_page
        mock_fitz_open.return_value = mock_doc

        parser = PdfParser()
        result = parser.parse("/tmp/test.pdf")

        assert result.page_count == 2
        assert "第一章 项目概述" in result.text
        assert "第二章 技术方案" in result.text
        assert result.is_scanned is False
        assert result.word_count > 0
        mock_page1.get_pixmap.assert_not_called()
        mock_doc.close.assert_called_once()

    @patch("app.ai.parsers.pdf_parser.fitz.open")
    @patch.object(PdfParser, "_get_ocr_engine")
    def test_scanned_pdf_fallback_to_ocr(self, mock_get_ocr: MagicMock, mock_fitz_open: MagicMock) -> None:
        """测试扫描件 PDF 回退到 PaddleOCR"""
        # Mock OCR 引擎
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [[["line1", ["扫描识别文本", 0.95]]]]
        mock_get_ocr.return_value = mock_ocr

        # Mock 文档（1页，文本极少，触发 OCR）
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=1)

        mock_page = MagicMock()
        mock_page.number = 0
        mock_page.get_text.return_value = "   "  # 空文本，触发 OCR

        mock_pix = MagicMock()
        mock_page.get_pixmap.return_value = mock_pix

        mock_doc.load_page = MagicMock(return_value=mock_page)
        mock_fitz_open.return_value = mock_doc

        parser = PdfParser()
        result = parser.parse("/tmp/test.pdf")

        assert result.page_count == 1
        assert result.is_scanned is True
        assert "扫描识别文本" in result.text
        mock_page.get_pixmap.assert_called_once_with(dpi=300)
        mock_ocr.ocr.assert_called_once()
        mock_doc.close.assert_called_once()

    @patch("app.ai.parsers.pdf_parser.fitz.open")
    def test_mixed_pdf(self, mock_fitz_open: MagicMock) -> None:
        """测试混合 PDF（第1页数字文本，第2页扫描件）"""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [[["line1", ["OCR识别结果", 0.95]]]]

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=2)

        # 第1页：数字文本
        mock_page1 = MagicMock()
        mock_page1.number = 0
        mock_page1.get_text.return_value = (
            "这是一段足够长的数字文本内容，超过阈值。"
            "本文档详细描述了项目的技术架构、实施方案和验收标准。"
            "项目采用敏捷开发模式，分三个阶段实施，总工期约十二个月。"
        )
        mock_page1.get_pixmap = MagicMock()

        # 第2页：扫描件（空文本）
        mock_page2 = MagicMock()
        mock_page2.number = 1
        mock_page2.get_text.return_value = "   "
        mock_pix = MagicMock()
        mock_page2.get_pixmap.return_value = mock_pix

        def load_page(idx: int) -> MagicMock:
            return [mock_page1, mock_page2][idx]

        mock_doc.load_page = load_page
        mock_fitz_open.return_value = mock_doc

        parser = PdfParser()
        parser._ocr_engine = mock_ocr  # 直接注入 mock

        result = parser.parse("/tmp/test.pdf")

        assert result.page_count == 2
        assert result.is_scanned is True
        assert "数字文本" in result.text
        assert "OCR识别结果" in result.text
        mock_page1.get_pixmap.assert_not_called()
        mock_page2.get_pixmap.assert_called_once()


class TestDocxParser:
    """DOCX 解析器测试"""

    @patch("app.ai.parsers.docx_parser.Document")
    def test_parse_paragraphs(self, mock_document_cls: MagicMock) -> None:
        """测试段落提取"""
        mock_doc = MagicMock()
        mock_para1 = MagicMock()
        mock_para1.text = "  第一段文本  "
        mock_para2 = MagicMock()
        mock_para2.text = "  "  # 空段落，应被过滤
        mock_para3 = MagicMock()
        mock_para3.text = "第二段文本"
        mock_doc.paragraphs = [mock_para1, mock_para2, mock_para3]
        mock_doc.tables = []
        mock_document_cls.return_value = mock_doc

        parser = DocxParser()
        result = parser.parse("/tmp/test.docx")

        assert "第一段文本" in result.text
        assert "第二段文本" in result.text
        assert result.word_count > 0
        assert result.page_count >= 1

    @patch("app.ai.parsers.docx_parser.Document")
    def test_parse_tables(self, mock_document_cls: MagicMock) -> None:
        """测试表格提取"""
        mock_doc = MagicMock()
        mock_doc.paragraphs = []

        # Mock 表格
        mock_cell1 = MagicMock()
        mock_cell1.text = "单元格1"
        mock_cell2 = MagicMock()
        mock_cell2.text = "单元格2"
        mock_row = MagicMock()
        mock_row.cells = [mock_cell1, mock_cell2]
        mock_table = MagicMock()
        mock_table.rows = [mock_row]
        mock_doc.tables = [mock_table]

        mock_document_cls.return_value = mock_doc

        parser = DocxParser()
        result = parser.parse("/tmp/test.docx")

        assert "单元格1 | 单元格2" in result.text


class TestImageParser:
    """图片解析器测试"""

    @patch.object(ImageParser, "_get_ocr_engine")
    def test_image_ocr(self, mock_get_ocr: MagicMock) -> None:
        """测试图片 OCR 识别"""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [
            [
                ["line1", ["图片文字第一行", 0.98]],
                ["line2", ["图片文字第二行", 0.97]],
            ]
        ]
        mock_get_ocr.return_value = mock_ocr

        parser = ImageParser()
        result = parser.parse("/tmp/test.png")

        assert "图片文字第一行" in result.text
        assert "图片文字第二行" in result.text
        assert result.page_count == 1
        assert result.is_scanned is True
        mock_ocr.ocr.assert_called_once_with("/tmp/test.png", cls=True)

    @patch.object(ImageParser, "_get_ocr_engine")
    def test_image_ocr_empty_result(self, mock_get_ocr: MagicMock) -> None:
        """测试图片 OCR 无识别结果"""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [None]
        mock_get_ocr.return_value = mock_ocr

        parser = ImageParser()
        result = parser.parse("/tmp/empty.png")

        assert result.text == ""
        assert result.word_count == 0
