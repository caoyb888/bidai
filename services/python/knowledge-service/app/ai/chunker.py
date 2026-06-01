# ============================================================
# 文档分块器 — 基于 tiktoken 的 Token 级切分
# 策略：TEXT 按 512 tokens / overlap 50 切分；TABLE 整体保留
# ============================================================

from dataclasses import dataclass
from typing import Literal

import tiktoken

from app.ai.parsers.base import DocumentFragment
from app.core.config import settings
from app.core.logging import logger

ChunkType = Literal["TEXT", "TABLE", "IMAGE_CAPTION"]


@dataclass
class Chunk:
    """分块结果"""

    content: str
    chunk_type: ChunkType
    token_count: int
    char_count: int
    page_no: int | None = None


class DocumentChunker:
    """文档分块器"""

    def __init__(
        self,
        chunk_size: int | None = None,
        overlap: int | None = None,
        max_tokens: int | None = None,
    ) -> None:
        self.chunk_size = chunk_size or settings.chunk_size_tokens
        self.overlap = overlap or settings.chunk_overlap_tokens
        self.max_tokens = max_tokens or settings.chunk_max_tokens
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception as exc:
            logger.warning("Failed to load tiktoken cl100k_base, falling back to p50k_base", extra={"error": str(exc)})
            self.encoding = tiktoken.get_encoding("p50k_base")

    def _count_tokens(self, text: str) -> int:
        """计算文本的 token 数"""
        return len(self.encoding.encode(text))

    def _split_text(self, text: str) -> list[str]:
        """将长文本按 chunk_size / overlap 切分为多个文本块"""
        tokens = self.encoding.encode(text)
        if len(tokens) <= self.chunk_size:
            return [text]

        chunks: list[str] = []
        start = 0
        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunks.append(self.encoding.decode(chunk_tokens))

            if end >= len(tokens):
                break

            start = end - self.overlap
            if start < 0:
                start = 0
            # 避免死循环：确保 start 向前移动
            if start >= end:
                start = end

        return chunks

    def _split_oversized_table(self, fragment: DocumentFragment) -> list[Chunk]:
        """对超长的表格按行拆分，保证每块不超过 max_tokens"""
        lines = fragment.content.split("\n")
        chunks: list[list[str]] = []
        current_lines: list[str] = []
        current_tokens = 0

        for line in lines:
            line_tokens = self._count_tokens(line)
            if line_tokens > self.max_tokens:
                # 单行就超过上限，强制加入（极端情况）
                if current_lines:
                    chunks.append(current_lines)
                    current_lines = []
                    current_tokens = 0
                chunks.append([line])
                continue

            if current_tokens + line_tokens > self.max_tokens and current_lines:
                chunks.append(current_lines)
                current_lines = []
                current_tokens = 0

            current_lines.append(line)
            current_tokens += line_tokens

        if current_lines:
            chunks.append(current_lines)

        result: list[Chunk] = []
        for chunk_lines in chunks:
            content = "\n".join(chunk_lines)
            result.append(
                Chunk(
                    content=content,
                    chunk_type="TABLE",
                    token_count=self._count_tokens(content),
                    char_count=len(content),
                    page_no=fragment.page_no if fragment.page_no > 0 else None,
                )
            )
        return result

    def chunk_fragments(self, fragments: list[DocumentFragment]) -> list[Chunk]:
        """
        对文档片段列表执行分块

        规则：
        1. TABLE 片段整体保留（若超长则按行拆分）
        2. TEXT 片段合并后按 512 tokens / overlap 50 切分
        """
        chunks: list[Chunk] = []

        # 收集所有 TEXT 内容
        text_parts: list[str] = []
        for frag in fragments:
            if frag.fragment_type == "TEXT":
                text_parts.append(frag.content)

        # 处理 TEXT 分块
        if text_parts:
            merged_text = "\n\n".join(text_parts)
            text_chunks = self._split_text(merged_text)
            for i, content in enumerate(text_chunks):
                token_count = self._count_tokens(content)
                # 确保不超过 max_tokens（理论上 split_text 已保证，但做一层保险）
                if token_count > self.max_tokens:
                    # 再切一次
                    sub_chunks = self._split_text(content)
                    for sub_content in sub_chunks:
                        chunks.append(
                            Chunk(
                                content=sub_content,
                                chunk_type="TEXT",
                                token_count=self._count_tokens(sub_content),
                                char_count=len(sub_content),
                                page_no=None,
                            )
                        )
                else:
                    chunks.append(
                        Chunk(
                            content=content,
                            chunk_type="TEXT",
                            token_count=token_count,
                            char_count=len(content),
                            page_no=None,
                        )
                    )

        # 处理 TABLE 分块（整体保留，超长按行拆分）
        for frag in fragments:
            if frag.fragment_type == "TABLE":
                token_count = self._count_tokens(frag.content)
                if token_count <= self.max_tokens:
                    chunks.append(
                        Chunk(
                            content=frag.content,
                            chunk_type="TABLE",
                            token_count=token_count,
                            char_count=len(frag.content),
                            page_no=frag.page_no if frag.page_no > 0 else None,
                        )
                    )
                else:
                    logger.warning(
                        "Oversized table detected, splitting by rows",
                        extra={
                            "page_no": frag.page_no,
                            "token_count": token_count,
                            "max_tokens": self.max_tokens,
                        },
                    )
                    table_chunks = self._split_oversized_table(frag)
                    chunks.extend(table_chunks)

        logger.info(
            "Document chunked",
            extra={
                "input_fragments": len(fragments),
                "output_chunks": len(chunks),
                "text_chunks": sum(1 for c in chunks if c.chunk_type == "TEXT"),
                "table_chunks": sum(1 for c in chunks if c.chunk_type == "TABLE"),
            },
        )

        return chunks
