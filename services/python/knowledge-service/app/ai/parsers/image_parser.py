# ============================================================
# 图片解析器 — PaddleOCR
# ============================================================

from typing import Any

from app.ai.parsers.base import DocumentParser, ParseResult, count_words
from app.core.logging import logger


class ImageParser(DocumentParser):
    """图片 OCR 解析器（JPG/PNG）"""

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
                logger.error("PaddleOCR not installed, cannot process images")
                raise RuntimeError("PaddleOCR is required for image OCR processing") from exc
        return self._ocr_engine

    def parse(self, file_path: str) -> ParseResult:
        """解析图片文件，返回 OCR 识别文本"""
        ocr = self._get_ocr_engine()

        result = ocr.ocr(file_path, cls=True)
        if result is None or result[0] is None:
            return ParseResult(text="", page_count=1, word_count=0, is_scanned=True)

        lines: list[str] = []
        for line in result[0]:
            if line is not None:
                lines.append(line[1][0])

        full_text = "\n".join(lines)
        word_count = count_words(full_text)

        logger.info(
            "Image OCR parsed",
            extra={
                "file_path": file_path,
                "word_count": word_count,
            },
        )

        return ParseResult(
            text=full_text,
            page_count=1,
            word_count=word_count,
            is_scanned=True,
        )
