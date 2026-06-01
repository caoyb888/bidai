# ============================================================
# OCR 解析模块
# ============================================================

from app.ai.parsers.base import DocumentFragment, DocumentParser, ParseResult, count_words
from app.ai.parsers.docx_parser import DocxParser
from app.ai.parsers.factory import UnsupportedFileTypeError, get_parser
from app.ai.parsers.image_parser import ImageParser
from app.ai.parsers.pdf_parser import PdfParser

__all__ = [
    "DocumentFragment",
    "DocumentParser",
    "ParseResult",
    "count_words",
    "get_parser",
    "PdfParser",
    "DocxParser",
    "ImageParser",
    "UnsupportedFileTypeError",
]
