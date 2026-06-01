# ============================================================
# DOCX 解析器 — python-docx
# 支持段落与表格结构化输出
# ============================================================

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.ai.parsers.base import DocumentFragment, DocumentParser, ParseResult, count_words
from app.core.logging import logger


class DocxParser(DocumentParser):
    """DOCX 文档解析器"""

    def parse(self, file_path: str) -> ParseResult:
        """解析 DOCX 文档，按顺序提取段落和表格片段"""

        doc = Document(file_path)
        fragments: list[DocumentFragment] = []

        # 遍历 body 中的所有子元素，保持原始阅读顺序
        try:
            body_elements = list(doc.element.body)
        except Exception:
            body_elements = []

        if body_elements:
            for element in body_elements:
                tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

                if tag == "p":
                    para = Paragraph(element, doc)
                    text = para.text.strip()
                    if text:
                        fragments.append(
                            DocumentFragment(
                                content=text,
                                page_no=0,
                                fragment_type="TEXT",
                            )
                        )

                elif tag == "tbl":
                    table = Table(element, doc)
                    rows: list[str] = []
                    for row in table.rows:
                        row_texts: list[str] = []
                        for cell in row.cells:
                            cell_text = cell.text.strip()
                            if cell_text:
                                row_texts.append(cell_text)
                        if row_texts:
                            rows.append(" | ".join(row_texts))

                    if rows:
                        table_text = "\n".join(rows)
                        fragments.append(
                            DocumentFragment(
                                content=table_text,
                                page_no=0,
                                fragment_type="TABLE",
                            )
                        )
        else:
            # 回退：直接遍历 paragraphs 和 tables
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    fragments.append(
                        DocumentFragment(
                            content=text,
                            page_no=0,
                            fragment_type="TEXT",
                        )
                    )

            for table in doc.tables:
                fallback_rows: list[str] = []
                for row in table.rows:
                    fallback_row_texts: list[str] = []
                    for cell in row.cells:
                        cell_text = cell.text.strip()
                        if cell_text:
                            fallback_row_texts.append(cell_text)
                    if fallback_row_texts:
                        fallback_rows.append(" | ".join(fallback_row_texts))

                if fallback_rows:
                    table_text = "\n".join(fallback_rows)
                    fragments.append(
                        DocumentFragment(
                            content=table_text,
                            page_no=0,
                            fragment_type="TABLE",
                        )
                    )

        full_text = "\n\n".join(f.content for f in fragments)
        word_count = count_words(full_text)

        # python-docx 没有直接获取页数的方法，按经验估算
        page_count = max(1, word_count // 500)

        logger.info(
            "DOCX parsed",
            extra={
                "file_path": file_path,
                "fragments": len(fragments),
                "text_fragments": sum(1 for f in fragments if f.fragment_type == "TEXT"),
                "table_fragments": sum(1 for f in fragments if f.fragment_type == "TABLE"),
                "word_count": word_count,
            },
        )

        return ParseResult(
            fragments=fragments,
            page_count=page_count,
            word_count=word_count,
            is_scanned=False,
        )
