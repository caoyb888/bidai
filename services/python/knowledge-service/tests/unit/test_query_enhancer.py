# ============================================================
# 单元测试：Query Enhancer
# ============================================================

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.query_enhancer import QueryEnhancer


class TestQueryEnhancer:
    """QueryEnhancer 单元测试"""

    async def test_short_query_unchanged(self) -> None:
        """测试短查询不增强"""
        enhancer = QueryEnhancer(llm_client=MagicMock())
        result = await enhancer.enhance("资质")
        assert result == "资质"

    async def test_llm_enhancement_success(self) -> None:
        """测试 LLM 增强成功"""
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value=MagicMock(content="  资质证书、资格等级、企业资质  "))

        enhancer = QueryEnhancer(llm_client=mock_llm)
        result = await enhancer.enhance("公司资质要求")

        assert "资质证书" in result
        mock_llm.chat.assert_called_once()

    async def test_llm_failure_fallback(self) -> None:
        """测试 LLM 失败时降级返回原查询"""
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(side_effect=Exception("LLM timeout"))

        enhancer = QueryEnhancer(llm_client=mock_llm)
        result = await enhancer.enhance("投标方案编写要求")

        assert result == "投标方案编写要求"

    async def test_empty_enhancement_fallback(self) -> None:
        """测试 LLM 返回空内容时降级"""
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value=MagicMock(content="   "))

        enhancer = QueryEnhancer(llm_client=mock_llm)
        result = await enhancer.enhance("投标方案编写要求")

        assert result == "投标方案编写要求"
