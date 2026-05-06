# ============================================================
# OCR 解析器抽象基类
# ============================================================

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ParseResult:
    """文档解析结果"""

    text: str
    page_count: int
    word_count: int
    is_scanned: bool = False


class DocumentParser(ABC):
    """文档解析器抽象基类"""

    @abstractmethod
    def parse(self, file_path: str) -> ParseResult:
        """
        解析文档，返回解析结果

        Args:
            file_path: 本地文件绝对路径

        Returns:
            ParseResult: 解析结果
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
