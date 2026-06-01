# ============================================================
# Embedding 客户端 — 调用外部 API
# 支持批量 embedding（单次 ≤ 100 条）
# ============================================================

from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import logger


class EmbeddingError(Exception):
    """Embedding 调用异常"""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class EmbeddingClient:
    """Embedding API 客户端"""

    def __init__(self) -> None:
        self.api_url = settings.embedding_api_url
        self.api_key = settings.embedding_api_key
        self.model = settings.embedding_model
        self.dim = settings.embedding_dim
        self.batch_size = settings.embedding_batch_size
        self.timeout = settings.embedding_timeout

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        批量获取文本的 embedding 向量

        Args:
            texts: 文本列表（长度 ≤ batch_size）

        Returns:
            list[list[float]]: 向量列表，与输入顺序一致

        Raises:
            EmbeddingError: API 调用失败
        """
        if not texts:
            return []

        if not self.api_url:
            logger.error("Embedding API URL not configured")
            raise EmbeddingError("Embedding API URL not configured")

        if len(texts) > self.batch_size:
            logger.warning(
                "Embedding batch too large, splitting",
                extra={"input_size": len(texts), "batch_size": self.batch_size},
            )
            results: list[list[float]] = []
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                batch_results = await self.embed(batch)
                results.extend(batch_results)
            return results

        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict[str, Any] = {
            "input": texts,
            "model": self.model,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Embedding API HTTP error",
                    extra={
                        "status_code": exc.response.status_code,
                        "response": exc.response.text,
                    },
                )
                raise EmbeddingError(
                    f"Embedding API returned {exc.response.status_code}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                logger.error("Embedding API request error", extra={"error": str(exc)})
                raise EmbeddingError(f"Embedding API request failed: {exc}") from exc

        data = resp.json()
        embeddings_data = data.get("data", [])
        if not embeddings_data:
            raise EmbeddingError("Embedding API returned empty data")

        # 按 index 排序，保证与输入顺序一致
        embeddings_data.sort(key=lambda x: x.get("index", 0))
        embeddings = [item["embedding"] for item in embeddings_data]

        usage = data.get("usage", {})
        logger.info(
            "Embedding batch completed",
            extra={
                "batch_size": len(texts),
                "prompt_tokens": usage.get("prompt_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "model": self.model,
            },
        )

        return embeddings
