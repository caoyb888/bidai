# ============================================================
# Cross-Encoder 重排序客户端 — 调用外部 Reranker API
# 支持标准 reranker 接口（Cohere / Jina / 私有化 vLLM 等）
# ============================================================

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import logger


class RerankerError(Exception):
    """Reranker API 调用异常"""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class RerankResult:
    """重排序结果项"""

    def __init__(self, index: int, score: float, chunk_id: str, text: str) -> None:
        self.index = index
        self.score = score
        self.chunk_id = chunk_id
        self.text = text


class RerankerClient:
    """Cross-Encoder 重排序客户端"""

    def __init__(self) -> None:
        self.api_url = settings.reranker_api_url
        self.api_key = settings.reranker_api_key
        self.model = settings.reranker_model
        self.timeout = settings.reranker_timeout

    def _is_configured(self) -> bool:
        return bool(self.api_url)

    async def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int | None = None,
    ) -> list[RerankResult]:
        """
        对候选结果进行 Cross-Encoder 重排序

        Args:
            query: 原始查询
            candidates: 候选结果列表，每项至少包含 chunk_id, content
            top_k: 返回前 N 个结果，None 则返回全部

        Returns:
            按相关度降序排列的结果列表
        """
        if not candidates:
            return []

        if not self._is_configured():
            logger.warning("Reranker API not configured, falling back to original order")
            return [
                RerankResult(
                    index=i,
                    score=candidate.get("score", 0.0),
                    chunk_id=candidate["chunk_id"],
                    text=candidate.get("content", ""),
                )
                for i, candidate in enumerate(candidates)
            ]

        texts = [c.get("content", "") for c in candidates]

        payload: dict[str, Any] = {
            "query": query,
            "documents": texts,
            "model": self.model,
            "top_n": top_k or len(candidates),
        }

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(self.api_url, headers=headers, json=payload)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Reranker API HTTP error",
                    extra={"status_code": exc.response.status_code, "response": exc.response.text},
                )
                raise RerankerError(
                    f"Reranker API returned {exc.response.status_code}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                logger.error("Reranker API request error", extra={"error": str(exc)})
                raise RerankerError(f"Reranker API request failed: {exc}") from exc

        data = resp.json()
        results = data.get("results", [])

        # 适配多种 reranker API 返回格式
        # Cohere / Jina 格式: results=[{"index": 0, "relevance_score": 0.95}, ...]
        # 统一转换为 RerankResult
        reranked: list[RerankResult] = []
        for r in results:
            idx = r.get("index", r.get("document", {}).get("index", 0))
            score = r.get("relevance_score", r.get("score", 0.0))
            candidate = candidates[idx]
            reranked.append(
                RerankResult(
                    index=idx,
                    score=float(score),
                    chunk_id=candidate["chunk_id"],
                    text=candidate.get("content", ""),
                )
            )

        logger.info(
            "Reranker completed",
            extra={
                "input_candidates": len(candidates),
                "output_count": len(reranked),
                "model": self.model,
            },
        )

        return reranked
