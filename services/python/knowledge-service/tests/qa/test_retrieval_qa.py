# ============================================================
# 知识库检索 QA 质量测试
# Sprint: S1-2-010
#
# 覆盖内容：
#   1. Golden Dataset 格式有效性校验
#   2. 评估框架指标计算逻辑（Mock 检索结果）
#   3. 真实检索评估（在有数据的服务环境中运行）
#   4. 测试报告生成与阈值判定
# ============================================================

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.hybrid_retriever import SearchResult
from tests.qa.retrieval_evaluator import (
    EvaluationReport,
    GoldenCase,
    RetrievalEvaluator,
    _is_hit,
    load_golden_dataset,
)


# ---------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------
@pytest.fixture
def sample_cases() -> list[GoldenCase]:
    """小样本 Golden Case 用于快速测试"""
    return [
        GoldenCase(
            query_id="T001",
            query="测试查询资质证书",
            category="QUALIFICATION",
            expected_doc_titles=["资质", "证书"],
            description="测试用例",
        ),
        GoldenCase(
            query_id="T002",
            query="测试查询业绩案例",
            category="PERFORMANCE",
            expected_doc_titles=["业绩", "案例"],
            description="测试用例",
        ),
    ]


@pytest.fixture
def mock_hit_results() -> list[SearchResult]:
    """Mock 命中结果"""
    return [
        SearchResult(
            chunk_id="c1",
            doc_id="d1",
            doc_title="公司资质证书一览",
            content="",
            page_no=1,
            score=0.95,
        ),
    ]


@pytest.fixture
def mock_miss_results() -> list[SearchResult]:
    """Mock 未命中结果"""
    return [
        SearchResult(
            chunk_id="c2",
            doc_id="d2",
            doc_title="完全无关的文档",
            content="",
            page_no=1,
            score=0.85,
        ),
    ]


# ---------------------------------------------------------------
# Golden Dataset 校验
# ---------------------------------------------------------------
class TestGoldenDataset:
    """Golden Dataset 基础校验"""

    def test_dataset_exists_and_valid(self) -> None:
        """golden_dataset.json 存在且格式正确，包含 20 条用例"""
        cases = load_golden_dataset()
        assert len(cases) == 20, f"期望 20 条用例，实际 {len(cases)} 条"

        for case in cases:
            assert case.query_id, "query_id 不能为空"
            assert case.query, "query 不能为空"
            assert case.expected_doc_titles, "expected_doc_titles 不能为空"
            assert case.category in {
                "QUALIFICATION",
                "PERFORMANCE",
                "PERSONNEL",
                "SOLUTION_TEMPLATE",
                None,
            }, f"未知分类: {case.category}"

    def test_dataset_categories_distribution(self) -> None:
        """分类覆盖度检查：4 大分类均有覆盖"""
        cases = load_golden_dataset()
        categories = {c.category for c in cases}
        assert "QUALIFICATION" in categories
        assert "PERFORMANCE" in categories
        assert "PERSONNEL" in categories
        assert "SOLUTION_TEMPLATE" in categories


# ---------------------------------------------------------------
# 命中判定逻辑
# ---------------------------------------------------------------
class TestIsHit:
    """测试 _is_hit 核心判定函数"""

    def test_hit_when_keyword_in_title(self) -> None:
        results = [
            SearchResult(
                chunk_id="c1",
                doc_id="d1",
                doc_title="信息系统集成资质证书",
                content="",
                page_no=1,
                score=0.9,
            ),
        ]
        hit, matched = _is_hit(results, ["资质", "证书"])
        assert hit is True
        assert "资质" in matched

    def test_hit_case_insensitive(self) -> None:
        results = [
            SearchResult(
                chunk_id="c1",
                doc_id="d1",
                doc_title="ISO9001 质量管理",
                content="",
                page_no=1,
                score=0.9,
            ),
        ]
        hit, matched = _is_hit(results, ["iso9001"])
        assert hit is True
        assert "iso9001" in [m.lower() for m in matched]

    def test_miss_when_no_keyword_match(self) -> None:
        results = [
            SearchResult(
                chunk_id="c1",
                doc_id="d1",
                doc_title="完全无关的内容",
                content="",
                page_no=1,
                score=0.9,
            ),
        ]
        hit, matched = _is_hit(results, ["资质", "证书"])
        assert hit is False
        assert matched == []

    def test_hit_across_multiple_results(self) -> None:
        results = [
            SearchResult(
                chunk_id="c1",
                doc_id="d1",
                doc_title="第一页",
                content="",
                page_no=1,
                score=0.9,
            ),
            SearchResult(
                chunk_id="c2",
                doc_id="d2",
                doc_title="CMMI 证书",
                content="",
                page_no=2,
                score=0.85,
            ),
        ]
        hit, matched = _is_hit(results, ["CMMI"])
        assert hit is True

    def test_empty_results_is_miss(self) -> None:
        hit, matched = _is_hit([], ["资质"])
        assert hit is False
        assert matched == []

    def test_empty_keywords_is_miss(self) -> None:
        results = [
            SearchResult(
                chunk_id="c1",
                doc_id="d1",
                doc_title="资质证书",
                content="",
                page_no=1,
                score=0.9,
            ),
        ]
        hit, matched = _is_hit(results, [])
        assert hit is False
        assert matched == []


# ---------------------------------------------------------------
# 评估器核心逻辑（Mock）
# ---------------------------------------------------------------
class TestEvaluatorLogic:
    """使用 Mock 检索结果验证评估框架指标计算"""

    @pytest.mark.asyncio
    async def test_all_hit_passes_threshold(
        self,
        sample_cases: list[GoldenCase],
    ) -> None:
        evaluator = RetrievalEvaluator(threshold=0.8)

        async def mock_retrieve(query: str, _top_k: int, _category: str | None) -> list[SearchResult]:
            # 根据查询返回匹配的结果
            title = "资质证书" if "资质" in query else "业绩案例"
            return [
                SearchResult(
                    chunk_id="c1",
                    doc_id="d1",
                    doc_title=title,
                    content="",
                    page_no=1,
                    score=0.9,
                ),
            ]

        report = await evaluator.evaluate(cases=sample_cases, retrieve_fn=mock_retrieve)

        assert report.total_cases == 2
        assert report.hit_count == 2
        assert report.hit_at_5 == 1.0
        assert report.passed is True

    @pytest.mark.asyncio
    async def test_all_miss_fails_threshold(
        self,
        sample_cases: list[GoldenCase],
        mock_miss_results: list[SearchResult],
    ) -> None:
        evaluator = RetrievalEvaluator(threshold=0.8)

        async def mock_retrieve(_query: str, _top_k: int, _category: str | None) -> list[SearchResult]:
            return mock_miss_results

        report = await evaluator.evaluate(cases=sample_cases, retrieve_fn=mock_retrieve)

        assert report.hit_count == 0
        assert report.hit_at_5 == 0.0
        assert report.passed is False

    @pytest.mark.asyncio
    async def test_partial_hit_50_percent(self, sample_cases: list[GoldenCase]) -> None:
        evaluator = RetrievalEvaluator(threshold=0.4)

        call_count = 0

        async def mock_retrieve(_query: str, _top_k: int, _category: str | None) -> list[SearchResult]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [
                    SearchResult(
                        chunk_id="c1",
                        doc_id="d1",
                        doc_title="资质证书",
                        content="",
                        page_no=1,
                        score=0.9,
                    ),
                ]
            return [
                SearchResult(
                    chunk_id="c2",
                    doc_id="d2",
                    doc_title="无关文档",
                    content="",
                    page_no=1,
                    score=0.8,
                ),
            ]

        report = await evaluator.evaluate(cases=sample_cases, retrieve_fn=mock_retrieve)

        assert report.hit_count == 1
        assert report.miss_count == 1
        assert report.hit_at_5 == 0.5
        assert report.passed is True

    @pytest.mark.asyncio
    async def test_retrieve_exception_handled(self, sample_cases: list[GoldenCase]) -> None:
        """检索异常不应导致评估中断"""
        evaluator = RetrievalEvaluator(threshold=0.0)

        async def mock_retrieve(_query: str, _top_k: int, _category: str | None) -> list[SearchResult]:
            raise RuntimeError("检索服务异常")

        report = await evaluator.evaluate(cases=sample_cases, retrieve_fn=mock_retrieve)

        assert report.total_cases == 2
        assert report.hit_count == 0
        assert report.miss_count == 2
        assert report.passed is True  # threshold=0.0 时仍通过

    @pytest.mark.asyncio
    async def test_report_contains_case_details(self, sample_cases: list[GoldenCase]) -> None:
        evaluator = RetrievalEvaluator(threshold=0.8)

        async def mock_retrieve(_query: str, _top_k: int, _category: str | None) -> list[SearchResult]:
            return [
                SearchResult(
                    chunk_id="c1",
                    doc_id="d1",
                    doc_title="资质证书",
                    content="",
                    page_no=1,
                    score=0.9,
                ),
            ]

        report = await evaluator.evaluate(cases=sample_cases, retrieve_fn=mock_retrieve)

        assert len(report.cases) == 2
        for case_report in report.cases:
            assert "query_id" in case_report
            assert "query" in case_report
            assert "hit" in case_report
            assert "top5_doc_titles" in case_report
            assert "duration_ms" in case_report

    def test_report_json_serialization(self) -> None:
        report = EvaluationReport(
            total_cases=20,
            hit_count=16,
            miss_count=4,
            hit_at_5=0.8,
            threshold=0.8,
            passed=True,
            cases=[],
            timestamp="2026-06-01T10:00:00",
        )
        json_str = report.to_json()
        data = json.loads(json_str)
        assert data["hit_at_5"] == 0.8
        assert data["passed"] is True
        assert data["total_cases"] == 20


# ---------------------------------------------------------------
# 真实检索评估（可选，依赖外部环境）
# ---------------------------------------------------------------
class TestRealRetrievalEvaluation:
    """
    真实检索评估

    条件：
    - 需要 knowledge-service 运行且知识库中有数据
    - 若知识库为空或检索不到结果，测试自动跳过
    """

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_retrieval_hit_at_5(self) -> None:
        """使用真实 HybridRetriever 执行 Golden Dataset 评估"""
        from app.ai.hybrid_retriever import HybridRetriever

        cases = load_golden_dataset()
        evaluator = RetrievalEvaluator(
            retriever=HybridRetriever(),
            threshold=0.80,
            top_k=5,
        )

        report = await evaluator.evaluate(cases=cases)

        # 输出详细报告到控制台（pytest 捕获后可查看）
        print("\n" + "=" * 60)
        print("知识库检索 Golden Dataset 评估报告")
        print("=" * 60)
        print(f"  总用例数:   {report.total_cases}")
        print(f"  命中数:     {report.hit_count}")
        print(f"  未命中数:   {report.miss_count}")
        print(f"  Hit@5:      {report.hit_at_5:.2%}")
        print(f"  阈值:       {report.threshold:.0%}")
        print(f"  是否通过:   {'✅ 通过' if report.passed else '❌ 未通过'}")
        print("=" * 60)

        for case in report.cases:
            status = "✅ 命中" if case["hit"] else "❌ 未命中"
            print(f"  [{case['query_id']}] {status} | {case['query'][:40]}")
            if not case["hit"]:
                print(f"      Top-5 结果: {case['top5_doc_titles']}")

        # 断言达标
        assert report.hit_at_5 >= report.threshold, (
            f"检索准确率 Hit@5 ({report.hit_at_5:.2%}) 低于阈值 "
            f"({report.threshold:.0%})"
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_save_report_to_file(self, tmp_path: Path) -> None:
        """评估报告可写入 JSON 文件"""
        cases = load_golden_dataset()
        evaluator = RetrievalEvaluator(threshold=0.80, top_k=5)

        report = await evaluator.evaluate(cases=cases)

        report_path = tmp_path / "retrieval_qa_report.json"
        report_path.write_text(report.to_json(), encoding="utf-8")

        assert report_path.exists()
        loaded = json.loads(report_path.read_text(encoding="utf-8"))
        assert loaded["total_cases"] == 20
        assert "hit_at_5" in loaded
        assert "cases" in loaded
