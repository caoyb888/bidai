# ============================================================
# OCR 解析器抽象基类
# ============================================================

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

FragmentType = Literal["TEXT", "TABLE", "IMAGE_CAPTION"]


@dataclass
class DocumentFragment:
    """文档结构化片段"""

    content: str
    page_no: int = 0
    fragment_type: FragmentType = "TEXT"
    section_title: str = ""


@dataclass
class ParseResult:
    """文档解析结果"""

    fragments: list[DocumentFragment] = field(default_factory=list)
    page_count: int = 0
    word_count: int = 0
    is_scanned: bool = False

    @property
    def text(self) -> str:
        """兼容属性：返回所有片段拼接后的纯文本"""
        return "\n\n".join(f.content for f in self.fragments)


class DocumentParser(ABC):
    """文档解析器抽象基类"""

    @abstractmethod
    def parse(self, file_path: str) -> ParseResult:
        """
        解析文档，返回结构化解析结果

        Args:
            file_path: 本地文件绝对路径

        Returns:
            ParseResult: 解析结果（含结构化片段列表）
        """
        ...


def count_words(text: str) -> int:
    """
    统计文本字数（中文字符 + 英文单词）

    中文：每个汉字计 1 字
    英文：每个单词计 1 字
    """
    import re

    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    english_words = len(re.findall(r"[a-zA-Z]+", text))
    return chinese_chars + english_words
