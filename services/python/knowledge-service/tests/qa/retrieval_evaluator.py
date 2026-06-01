# ============================================================
# 知识库检索质量评估框架
# Sprint: S1-2-010
#
# 评估指标：Hit@5
#   - 对每条查询，若 Top-5 结果中至少有一条结果的 doc_title 包含任一期望关键词，
#     则视为命中（Hit）。
#   - 准确率 = 命中查询数 / 总查询数
#   - 阈值：≥ 80%
# ============================================================

from __future__ import annotations

import json
from collections.abc import Callable, Coroutine
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.ai.hybrid_retriever import HybridRetriever, SearchResult


# ---------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------
@dataclass
class GoldenCase:
    """Golden Dataset 单条用例"""

    query_id: str
    query: str
    category: str | None
    expected_doc_titles: list[str]
    description: str


@dataclass
class CaseResult:
    """单条用例评估结果"""

    query_id: str
    query: str
    category: str | None
    hit: bool
    top5_doc_titles: list[str]
    matched_keywords: list[str]
    duration_ms: float


@dataclass
class EvaluationReport:
    """评估汇总报告"""

    total_cases: int
    hit_count: int
    miss_count: int
    hit_at_5: float
    threshold: float
    passed: bool
    cases: list[dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ---------------------------------------------------------------
# Golden Dataset 加载
# ---------------------------------------------------------------
_GOLDEN_DATASET_PATH = Path(__file__).with_name("golden_dataset.json")


def load_golden_dataset(path: Path | None = None) -> list[GoldenCase]:
    """加载 Golden Dataset"""
    dataset_path = path or _GOLDEN_DATASET_PATH
    if not dataset_path.exists():
        raise FileNotFoundError(f"Golden Dataset 未找到: {dataset_path}")

    raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    return [
        GoldenCase(
            query_id=item["query_id"],
            query=item["query"],
            category=item.get("category"),
            expected_doc_titles=item["expected_doc_titles"],
            description=item.get("description", ""),
        )
        for item in raw
    ]


# ---------------------------------------------------------------
# 命中判定逻辑
# ---------------------------------------------------------------
def _is_hit(search_results: list[SearchResult], expected_keywords: list[str]) -> tuple[bool, list[str]]:
    """
    判定 Top-5 结果是否命中

    规则：任一结果 doc_title 包含任一期望关键词（不区分大小写）即视为命中
    """
    keywords_lower = [k.lower() for k in expected_keywords]
    matched: list[str] = []

    for result in search_results:
        title = (result.doc_title or "").lower()
        for kw in keywords_lower:
            if kw in title and kw not in matched:
                matched.append(kw)
        if matched:
            return True, matched

    return False, matched


# ---------------------------------------------------------------
# 评估器
# ---------------------------------------------------------------
class RetrievalEvaluator:
    """检索质量评估器"""

    def __init__(
        self,
        retriever: HybridRetriever | None = None,
        threshold: float = 0.80,
        top_k: int = 5,
    ) -> None:
        self.retriever = retriever or HybridRetriever()
        self.threshold = threshold
        self.top_k = top_k

    async def evaluate(
        self,
        cases: list[GoldenCase] | None = None,
        retrieve_fn: Callable[[str, int, str | None], Coroutine[Any, Any, list[SearchResult]]] | None = None,
    ) -> EvaluationReport:
        """
        执行评估

        Args:
            cases: Golden Dataset 用例列表，默认加载 golden_dataset.json
            retrieve_fn: 自定义检索函数签名 (query, top_k, category) -> list[SearchResult]
        """
        import time
        from datetime import datetime

        cases = cases or load_golden_dataset()
        if not cases:
            raise ValueError("Golden Dataset 为空")

        retrieve = retrieve_fn or self._default_retrieve
        case_results: list[CaseResult] = []

        for case in cases:
            start = time.perf_counter()
            try:
                results = await retrieve(case.query, self.top_k, case.category)
            except Exception:
                # 检索异常视为未命中，但保留空结果用于报告
                results = []
                case_results.append(
                    CaseResult(
                        query_id=case.query_id,
                        query=case.query,
                        category=case.category,
                        hit=False,
                        top5_doc_titles=[],
                        matched_keywords=[],
                        duration_ms=(time.perf_counter() - start) * 1000,
                    )
                )
                continue

            hit, matched = _is_hit(results, case.expected_doc_titles)
            case_results.append(
                CaseResult(
                    query_id=case.query_id,
                    query=case.query,
                    category=case.category,
                    hit=hit,
                    top5_doc_titles=[r.doc_title for r in results[: self.top_k]],
                    matched_keywords=matched,
                    duration_ms=(time.perf_counter() - start) * 1000,
                )
            )

        hit_count = sum(1 for r in case_results if r.hit)
        total = len(cases)
        hit_at_5 = hit_count / total if total > 0 else 0.0

        report = EvaluationReport(
            total_cases=total,
            hit_count=hit_count,
            miss_count=total - hit_count,
            hit_at_5=round(hit_at_5, 4),
            threshold=self.threshold,
            passed=hit_at_5 >= self.threshold,
            cases=[asdict(r) for r in case_results],
            timestamp=datetime.now().isoformat(),
        )
        return report

    async def _default_retrieve(
        self,
        query: str,
        top_k: int,
        category: str | None,
    ) -> list[SearchResult]:
        """默认使用 HybridRetriever 进行检索"""
        return await self.retriever.retrieve(
            query=query,
            top_k=top_k,
            doc_category=category,
        )
