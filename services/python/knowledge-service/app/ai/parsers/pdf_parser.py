# ============================================================
# PDF 解析器 — PyMuPDF + PaddleOCR 扫描件回退
# ============================================================

from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from app.ai.parsers.base import DocumentParser, ParseResult, count_words
from app.core.logging import logger

# 每页最少字符数阈值，低于此值判定为扫描件页
SCANNED_PAGE_CHAR_THRESHOLD = 50


class PdfParser(DocumentParser):
    """PDF 文档解析器"""

    def __init__(self) -> None:
        self._ocr_engine: Any | None = None

    def _get_ocr_engine(self) -> Any:
        """懒加载 PaddleOCR 引擎"""
        if self._ocr_engine is None:
            try:
                from paddleocr import PaddleOCR

                self._ocr_engine = PaddleOCR(
                    use_angle_cls=True,
                    lang="ch",
                    show_log=False,
                )
            except ImportError as exc:
                logger.error("PaddleOCR not installed, cannot process scanned PDF pages")
                raise RuntimeError("PaddleOCR is required for scanned PDF processing") from exc
        return self._ocr_engine

    def parse(self, file_path: str) -> ParseResult:
        """
        解析 PDF 文档

        策略：
        1. 逐页用 PyMuPDF 提取文本
        2. 若某页字符数 >= 50，视为数字文本页
        3. 若某页字符数 < 50，视为扫描件页，渲染为图片后用 PaddleOCR 识别
        4. 按页合并结果
        """
        doc = fitz.open(file_path)
        total_pages = len(doc)
        page_texts: list[str] = []
        scanned_pages = 0

        for page_idx in range(total_pages):
            page = doc.load_page(page_idx)
            text = page.get_text()
            text_stripped = text.strip()

            if len(text_stripped) >= SCANNED_PAGE_CHAR_THRESHOLD:
                # 数字文本页
                page_texts.append(f"--- Page {page_idx + 1} ---\n{text_stripped}")
            else:
                # 扫描件页：渲染为图片后 OCR
                scanned_pages += 1
                ocr_text = self._ocr_page(page)
                page_texts.append(f"--- Page {page_idx + 1} ---\n{ocr_text}")

        doc.close()

        full_text = "\n\n".join(page_texts)
        word_count = count_words(full_text)

        logger.info(
            "PDF parsed",
            extra={
                "file_path": file_path,
                "total_pages": total_pages,
                "scanned_pages": scanned_pages,
                "word_count": word_count,
            },
        )

        return ParseResult(
            text=full_text,
            page_count=total_pages,
            word_count=word_count,
            is_scanned=scanned_pages > 0,
        )

    def _ocr_page(self, page: Any) -> str:
        """对单页进行 OCR 识别"""
        ocr = self._get_ocr_engine()

        # 渲染页面为图片（DPI 300 保证识别精度）
        pix = page.get_pixmap(dpi=300)
        img_path = f"/tmp/paddleocr_{page.number}.png"
        pix.save(img_path)

        try:
            result = ocr.ocr(img_path, cls=True)
            if result is None or result[0] is None:
                return ""

            lines: list[str] = []
            for line in result[0]:
                if line is not None:
                    lines.append(line[1][0])
            return "\n".join(lines)
        finally:
            # 清理临时图片
            Path(img_path).unlink(missing_ok=True)
