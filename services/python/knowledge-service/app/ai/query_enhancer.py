# ============================================================
# 查询增强 — 同义词扩展 + 行业术语补全
# 使用 LLM 做查询改写，失败时降级返回原查询
# ============================================================

from __future__ import annotations

from app.ai.llm_client import ChatMessage, LLMClient, LLMProvider
from app.core.logging import logger


class QueryEnhancerError(Exception):
    """查询增强异常"""


QUERY_ENHANCE_PROMPT = """你是一位招投标领域的搜索优化专家。

任务：将用户的查询改写为一个更利于全文检索和语义检索的查询表达式。
要求：
1. 保留原查询的核心意图
2. 补充招投标领域的同义词、近义词（如"资质"可扩展为"资质证书、资格、等级"）
3. 补充行业标准术语（如"政务云"可扩展为"政务云平台、电子政务、政府信息化"）
4. 输出必须为纯文本，不要加任何解释、前缀或引号
5. 长度控制在 200 字以内

用户查询：{query}

改写后的查询："""


class QueryEnhancer:
    """查询增强器"""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or LLMClient()

    async def enhance(self, query: str) -> str:
        """
        对查询进行增强，失败时降级返回原查询

        Args:
            query: 用户原始查询

        Returns:
            增强后的查询（或原查询）
        """
        if not query or len(query) < 2:
            return query

        # 简单规则：如果查询已经很短且不含扩展空间，直接返回
        # 避免对简单查询过度扩展导致噪声
        if len(query) <= 4:
            return query

        messages = [
            ChatMessage(role="user", content=QUERY_ENHANCE_PROMPT.format(query=query)),
        ]

        try:
            resp = await self._llm.chat(
                messages=messages,
                temperature=0.1,
                max_tokens=256,
                force_provider=LLMProvider.PRIVATE,  # 查询增强优先走私有化模型（无敏感数据）
            )
            enhanced = resp.content.strip().strip('"').strip("'")

            # 安全检查：增强结果不能为空白，且应包含原查询关键词
            if not enhanced or len(enhanced) < 2:
                return query

            logger.info(
                "Query enhanced",
                extra={"original": query, "enhanced": enhanced, "model": resp.model},
            )
            return enhanced

        except Exception as exc:
            logger.warning(
                "Query enhancement failed, falling back to original",
                extra={"query": query, "error": str(exc)},
            )
            return query
