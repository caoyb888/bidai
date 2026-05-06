# ============================================================
# 解析器工厂 — 根据 mime_type 路由到对应解析器
# ============================================================

from app.ai.parsers.base import DocumentParser
from app.ai.parsers.docx_parser import DocxParser
from app.ai.parsers.image_parser import ImageParser
from app.ai.parsers.pdf_parser import PdfParser
from app.core.exceptions import BaseServiceException


class UnsupportedFileTypeError(BaseServiceException):
    """不支持的文件类型（错误码 30004）"""

    def __init__(self, mime_type: str) -> None:
        super().__init__(
            code=30004,
            message="文件类型不支持 OCR 解析",
            detail=f"不支持的 MIME 类型: {mime_type}",
            status_code=422,
        )


PARSER_MAP: dict[str, type[DocumentParser]] = {
    "application/pdf": PdfParser,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocxParser,
    "image/jpeg": ImageParser,
    "image/png": ImageParser,
}


def get_parser(mime_type: str) -> DocumentParser:
    """
    根据 MIME 类型获取对应的文档解析器

    Args:
        mime_type: 文件 MIME 类型

    Returns:
        DocumentParser: 对应的解析器实例

    Raises:
        UnsupportedFileTypeError: 不支持的文件类型
    """
    parser_cls = PARSER_MAP.get(mime_type)
    if parser_cls is None:
        raise UnsupportedFileTypeError(mime_type)
    return parser_cls()
