# ============================================================
# 单元测试：文档分块器
# ============================================================


from app.ai.chunker import DocumentChunker
from app.ai.parsers.base import DocumentFragment


class TestDocumentChunker:
    """文档分块器测试"""

    def test_text_chunking_basic(self) -> None:
        """测试基本文本分块"""
        chunker = DocumentChunker(chunk_size=20, overlap=5, max_tokens=30)

        # 构造一个约 60 tokens 的长文本（英文单词约 1 token/词）
        long_text = " ".join([f"word{i}" for i in range(60)])
        fragments = [DocumentFragment(content=long_text, page_no=1, fragment_type="TEXT")]

        chunks = chunker.chunk_fragments(fragments)

        assert len(chunks) >= 2
        for chunk in chunks:
            assert chunk.chunk_type == "TEXT"
            assert chunk.token_count <= chunker.max_tokens
            assert chunk.token_count > 0
            assert chunk.char_count > 0

    def test_table_preserved_as_whole(self) -> None:
        """测试表格整体保留不切分"""
        chunker = DocumentChunker(chunk_size=10, overlap=2, max_tokens=50)

        table_text = "col1 | col2 | col3\nval1 | val2 | val3\nval4 | val5 | val6"
        fragments = [DocumentFragment(content=table_text, page_no=1, fragment_type="TABLE")]

        chunks = chunker.chunk_fragments(fragments)

        assert len(chunks) == 1
        assert chunks[0].chunk_type == "TABLE"
        assert table_text in chunks[0].content

    def test_mixed_text_and_table(self) -> None:
        """测试文本和表格混合场景"""
        chunker = DocumentChunker(chunk_size=20, overlap=5, max_tokens=30)

        text1 = " ".join([f"text{i}" for i in range(30)])
        table = "A | B\n1 | 2"
        text2 = " ".join([f"more{i}" for i in range(30)])

        fragments = [
            DocumentFragment(content=text1, page_no=1, fragment_type="TEXT"),
            DocumentFragment(content=table, page_no=1, fragment_type="TABLE"),
            DocumentFragment(content=text2, page_no=2, fragment_type="TEXT"),
        ]

        chunks = chunker.chunk_fragments(fragments)

        table_chunks = [c for c in chunks if c.chunk_type == "TABLE"]
        text_chunks = [c for c in chunks if c.chunk_type == "TEXT"]

        assert len(table_chunks) == 1
        assert table_chunks[0].content == table
        assert len(text_chunks) >= 1

    def test_empty_fragments(self) -> None:
        """测试空片段列表"""
        chunker = DocumentChunker()
        chunks = chunker.chunk_fragments([])
        assert chunks == []

    def test_oversized_table_split_by_rows(self) -> None:
        """测试超长表格按行拆分"""
        chunker = DocumentChunker(chunk_size=10, overlap=2, max_tokens=20)

        # 构造一个很多行的表格，总 token 数超过 max_tokens
        rows = [f"column_a{i} | column_b{i} | column_c{i}" for i in range(50)]
        table_text = "\n".join(rows)
        fragments = [DocumentFragment(content=table_text, page_no=1, fragment_type="TABLE")]

        chunks = chunker.chunk_fragments(fragments)

        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.chunk_type == "TABLE"
            assert chunk.token_count <= chunker.max_tokens

    def test_token_count_accuracy(self) -> None:
        """测试 token 计数准确性（使用 tiktoken）"""
        chunker = DocumentChunker()

        text = "Hello world, this is a test sentence for token counting."
        fragments = [DocumentFragment(content=text, page_no=1, fragment_type="TEXT")]

        chunks = chunker.chunk_fragments(fragments)

        assert len(chunks) == 1
        # 使用相同的 encoding 验证
        expected_tokens = len(chunker.encoding.encode(text))
        assert chunks[0].token_count == expected_tokens

    def test_overlap_preserves_context(self) -> None:
        """测试 overlap 保留上下文"""
        chunker = DocumentChunker(chunk_size=10, overlap=5, max_tokens=20)

        words = [f"token{i}" for i in range(30)]
        text = " ".join(words)
        fragments = [DocumentFragment(content=text, page_no=1, fragment_type="TEXT")]

        chunks = chunker.chunk_fragments(fragments)

        assert len(chunks) >= 2
        # 检查相邻 chunk 是否有重叠内容
        chunk0_tokens = chunker.encoding.encode(chunks[0].content)
        chunk1_tokens = chunker.encoding.encode(chunks[1].content)
        # 第二个 chunk 应该以第一个 chunk 末尾的某些 token 开头
        overlap_found = False
        for i in range(1, min(len(chunk0_tokens), len(chunk1_tokens))):
            if chunk0_tokens[-i:] == chunk1_tokens[:i]:
                overlap_found = True
                break
        assert overlap_found, "Adjacent chunks should have overlapping tokens"

    def test_page_no_preserved_for_table(self) -> None:
        """测试表格的 page_no 被保留"""
        chunker = DocumentChunker()

        fragments = [DocumentFragment(content="A | B", page_no=5, fragment_type="TABLE")]
        chunks = chunker.chunk_fragments(fragments)

        assert chunks[0].page_no == 5
