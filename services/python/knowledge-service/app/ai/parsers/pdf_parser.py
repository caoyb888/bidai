# ============================================================
# PDF 解析器 — PyMuPDF + PaddleOCR 扫描件回退
# 支持表格检测与结构化输出
# ============================================================

from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from app.ai.parsers.base import DocumentFragment, DocumentParser, ParseResult, count_words
from app.core.logging import logger

# 每页最少字符数阈值，低于此值判定为扫描件页
SCANNED_PAGE_CHAR_THRESHOLD = 50


def _extract_table_text(tab: Any) -> str:
    """从 PyMuPDF 表格对象提取文本（Markdown 风格）"""
    try:
        rows: list[list[str]] = tab.extract()
    except Exception:
        return ""

    lines: list[str] = []
    for row in rows:
        if not row:
            continue
        cells = [str(cell).strip() if cell is not None else "" for cell in row]
        # 过滤空行
        if any(cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def _extract_page_fragments(page: fitz.Page, page_idx: int) -> list[DocumentFragment]:
    """提取单页的结构化片段（文本 + 表格）"""
    fragments: list[DocumentFragment] = []

    # 1. 查找表格
    try:
        tabs = page.find_tables()
        table_bboxes = [tab.bbox for tab in tabs.tables] if tabs and tabs.tables else []
    except Exception:
        table_bboxes = []

    # 2. 获取所有文本块（按阅读顺序）
    blocks = page.get_text("blocks")
    if not isinstance(blocks, list) or not blocks:
        # 回退：将整个页面文本作为一个 TEXT fragment
        page_text = page.get_text().strip()
        if page_text:
            fragments.append(
                DocumentFragment(
                    content=page_text,
                    page_no=page_idx + 1,
                    fragment_type="TEXT",
                )
            )
        # 仍然尝试提取表格
        if table_bboxes:
            try:
                tabs = page.find_tables()
                for tab in tabs.tables:
                    table_text = _extract_table_text(tab)
                    if table_text:
                        fragments.append(
                            DocumentFragment(
                                content=table_text,
                                page_no=page_idx + 1,
                                fragment_type="TABLE",
                            )
                        )
            except Exception:
                pass
        return fragments

    blocks = sorted(blocks, key=lambda b: (b[1], b[0]))  # 按 y, x 排序

    # 3. 遍历文本块，判断是否在表格区域内
    for block in blocks:
        bbox = fitz.Rect(block[:4])
        text = block[4].strip()
        if not text:
            continue

        # 检查是否在表格区域内
        in_table = False
        for tab_bbox in table_bboxes:
            if bbox.intersects(fitz.Rect(tab_bbox)):
                in_table = True
                break

        if in_table:
            # 跳过在表格内的文本块，稍后统一提取表格
            continue

        fragments.append(
            DocumentFragment(
                content=text,
                page_no=page_idx + 1,
                fragment_type="TEXT",
            )
        )

    # 4. 提取表格（整体保留）
    if table_bboxes:
        try:
            tabs = page.find_tables()
            for tab in tabs.tables:
                table_text = _extract_table_text(tab)
                if table_text:
                    fragments.append(
                        DocumentFragment(
                            content=table_text,
                            page_no=page_idx + 1,
                            fragment_type="TABLE",
                        )
                    )
        except Exception:
            pass

    return fragments


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
        1. 逐页用 PyMuPDF 提取文本和表格
        2. 表格整体保留为 TABLE fragment
        3. 若某页字符数 < 50，视为扫描件页，渲染为图片后用 PaddleOCR 识别
        4. 按页合并结果
        """
        doc = fitz.open(file_path)
        total_pages = len(doc)
        all_fragments: list[DocumentFragment] = []
        scanned_pages = 0

        for page_idx in range(total_pages):
            page = doc.load_page(page_idx)
            text = page.get_text()
            text_stripped = text.strip()

            if len(text_stripped) >= SCANNED_PAGE_CHAR_THRESHOLD:
                # 数字文本页：结构化提取（文本 + 表格）
                page_frags = _extract_page_fragments(page, page_idx)
                all_fragments.extend(page_frags)
            else:
                # 扫描件页：渲染为图片后 OCR
                scanned_pages += 1
                ocr_text = self._ocr_page(page)
                if ocr_text.strip():
                    all_fragments.append(
                        DocumentFragment(
                            content=ocr_text,
                            page_no=page_idx + 1,
                            fragment_type="TEXT",
                        )
                    )

        doc.close()

        full_text = "\n\n".join(f.content for f in all_fragments)
        word_count = count_words(full_text)

        logger.info(
            "PDF parsed",
            extra={
                "file_path": file_path,
                "total_pages": total_pages,
                "scanned_pages": scanned_pages,
                "word_count": word_count,
                "fragments": len(all_fragments),
            },
        )

        return ParseResult(
            fragments=all_fragments,
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
