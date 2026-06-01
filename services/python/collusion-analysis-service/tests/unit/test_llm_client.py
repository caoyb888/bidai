# ============================================================
# LLMClient 单元测试
# 覆盖：敏感数据检测、Provider 初始化、降级链、异常处理
# ============================================================

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.llm_client import (
    ChatMessage,
    LLMAPIError,
    LLMClient,
    LLMProvider,
    LLMResponse,
    LLMTimeoutError,
    SensitiveDataGuard,
    SensitiveDataViolationError,
)


# ----------------------------------------------------------
# SensitiveDataGuard
# ----------------------------------------------------------
class TestSensitiveDataGuard:
    def test_private_provider_always_allowed(self) -> None:
        text = "身份证号 110101199001011234 手机号 13800138000"
        # 私有化模型不检测敏感数据
        SensitiveDataGuard.check(text, LLMProvider.PRIVATE)

    def test_external_provider_blocks_id_number(self) -> None:
        with pytest.raises(SensitiveDataViolationError):
            SensitiveDataGuard.check(
                "投标人身份证号 110101199001011234", LLMProvider.KIMI
            )

    def test_external_provider_blocks_phone(self) -> None:
        with pytest.raises(SensitiveDataViolationError):
            SensitiveDataGuard.check(
                "联系人电话 13800138000", LLMProvider.DEEPSEEK
            )

    def test_external_provider_blocks_amount(self) -> None:
        with pytest.raises(SensitiveDataViolationError):
            SensitiveDataGuard.check(
                "投标报价 5000000元", LLMProvider.KIMI
            )

    def test_safe_text_passes(self) -> None:
        text = "请提取以下招标文件的约束条件。"
        SensitiveDataGuard.check(text, LLMProvider.KIMI)
        SensitiveDataGuard.check(text, LLMProvider.DEEPSEEK)


# ----------------------------------------------------------
# LLMClient Provider 初始化
# ----------------------------------------------------------
class TestLLMClientInit:
    def test_no_providers_when_no_config(self) -> None:
        with patch(
            "app.ai.llm_client.settings"
        ) as mock_settings:
            mock_settings.llm_private_base_url = ""
            mock_settings.llm_private_model = ""
            mock_settings.llm_kimi_api_key = ""
            mock_settings.llm_deepseek_api_key = ""

            client = LLMClient()
            assert client._providers == []

    def test_kimi_provider_when_key_present(self) -> None:
        with patch("app.ai.llm_client.settings") as mock_settings:
            mock_settings.llm_private_base_url = ""
            mock_settings.llm_private_model = ""
            mock_settings.llm_kimi_api_key = "sk-test"
            mock_settings.llm_deepseek_api_key = ""

            client = LLMClient()
            assert client._providers == [LLMProvider.KIMI]

    def test_deepseek_provider_when_key_present(self) -> None:
        with patch("app.ai.llm_client.settings") as mock_settings:
            mock_settings.llm_private_base_url = ""
            mock_settings.llm_private_model = ""
            mock_settings.llm_kimi_api_key = ""
            mock_settings.llm_deepseek_api_key = "sk-test"

            client = LLMClient()
            assert client._providers == [LLMProvider.DEEPSEEK]

    def test_private_priority_over_external(self) -> None:
        with patch("app.ai.llm_client.settings") as mock_settings:
            mock_settings.llm_private_base_url = "http://gpu:8080/v1"
            mock_settings.llm_private_model = "qwen2.5-72b"
            mock_settings.llm_kimi_api_key = "sk-test"
            mock_settings.llm_deepseek_api_key = "sk-test"

            client = LLMClient()
            assert client._providers == [
                LLMProvider.PRIVATE,
                LLMProvider.KIMI,
                LLMProvider.DEEPSEEK,
            ]


# ----------------------------------------------------------
# LLMClient Chat 降级链
# ----------------------------------------------------------
class TestLLMClientChatFallback:
    @pytest.fixture
    def client(self) -> LLMClient:
        with patch("app.ai.llm_client.settings") as mock_settings:
            mock_settings.llm_private_base_url = ""
            mock_settings.llm_private_model = ""
            mock_settings.llm_kimi_api_key = "sk-kimi"
            mock_settings.llm_kimi_model = "moonshot-v1-8k"
            mock_settings.llm_kimi_timeout = 60
            mock_settings.llm_deepseek_api_key = "sk-ds"
            mock_settings.llm_deepseek_model = "deepseek-chat"
            mock_settings.llm_deepseek_timeout = 60
            return LLMClient()

    @pytest.mark.asyncio
    async def test_all_providers_fail_raises_error(self, client: LLMClient) -> None:
        with patch.object(
            client, "_call_kimi", side_effect=LLMTimeoutError("timeout")
        ), patch.object(
            client, "_call_deepseek", side_effect=LLMAPIError("api error")
        ):
            with pytest.raises(LLMAPIError) as exc_info:
                await client.chat([ChatMessage(role="user", content="hello")])
            assert "所有 LLM Provider 均不可用" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fallback_to_deepseek_when_kimi_fails(self, client: LLMClient) -> None:
        kimi_mock = AsyncMock(side_effect=LLMTimeoutError("kimi timeout"))
        deepseek_resp = LLMResponse(
            content="deepseek says hi",
            model="deepseek-chat",
            provider=LLMProvider.DEEPSEEK,
        )
        deepseek_mock = AsyncMock(return_value=deepseek_resp)

        with patch.object(client, "_call_kimi", kimi_mock), patch.object(
            client, "_call_deepseek", deepseek_mock
        ):
            result = await client.chat(
                [ChatMessage(role="user", content="hello")]
            )
            assert result.content == "deepseek says hi"
            assert result.provider == LLMProvider.DEEPSEEK
            kimi_mock.assert_awaited_once()
            deepseek_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_primary_success_no_fallback(self, client: LLMClient) -> None:
        kimi_resp = LLMResponse(
            content="kimi says hi",
            model="moonshot-v1-8k",
            provider=LLMProvider.KIMI,
        )
        kimi_mock = AsyncMock(return_value=kimi_resp)
        deepseek_mock = AsyncMock()

        with patch.object(client, "_call_kimi", kimi_mock), patch.object(
            client, "_call_deepseek", deepseek_mock
        ):
            result = await client.chat(
                [ChatMessage(role="user", content="hello")]
            )
            assert result.content == "kimi says hi"
            assert result.provider == LLMProvider.KIMI
            deepseek_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_provider(self, client: LLMClient) -> None:
        deepseek_resp = LLMResponse(
            content="forced deepseek",
            model="deepseek-chat",
            provider=LLMProvider.DEEPSEEK,
        )
        deepseek_mock = AsyncMock(return_value=deepseek_resp)
        kimi_mock = AsyncMock(side_effect=LLMTimeoutError("should not call"))

        with patch.object(client, "_call_kimi", kimi_mock), patch.object(
            client, "_call_deepseek", deepseek_mock
        ):
            result = await client.chat(
                [ChatMessage(role="user", content="hello")],
                force_provider=LLMProvider.DEEPSEEK,
            )
            assert result.provider == LLMProvider.DEEPSEEK
            kimi_mock.assert_not_called()


# ----------------------------------------------------------
# LLMClient 敏感数据拦截
# ----------------------------------------------------------
class TestLLMClientSensitiveBlock:
    @pytest.fixture
    def client(self) -> LLMClient:
        with patch("app.ai.llm_client.settings") as mock_settings:
            mock_settings.llm_private_base_url = ""
            mock_settings.llm_private_model = ""
            mock_settings.llm_kimi_api_key = "sk-kimi"
            mock_settings.llm_deepseek_api_key = "sk-ds"
            return LLMClient()

    @pytest.mark.asyncio
    async def test_external_blocked_on_sensitive_data(self, client: LLMClient) -> None:
        with pytest.raises(SensitiveDataViolationError):
            await client.chat(
                [
                    ChatMessage(
                        role="user",
                        content="投标人身份证号 110101199001011234",
                    )
                ],
                force_provider=LLMProvider.KIMI,
            )

    @pytest.mark.asyncio
    async def test_private_allowed_on_sensitive_data(self, client: LLMClient) -> None:
        # 即使内容含敏感信息，私有化模型也允许
        with patch.object(
            client,
            "_call_private",
            new_callable=AsyncMock,
            return_value=LLMResponse(
                content="ok",
                model="qwen",
                provider=LLMProvider.PRIVATE,
            ),
        ) as mock_private:
            with patch("app.ai.llm_client.settings") as mock_settings:
                mock_settings.llm_private_base_url = "http://gpu:8080/v1"
                mock_settings.llm_private_model = "qwen2.5"
                client_with_private = LLMClient()

            with patch.object(
                client_with_private, "_call_private", mock_private
            ):
                result = await client_with_private.chat(
                    [
                        ChatMessage(
                            role="user",
                            content="投标人身份证号 110101199001011234",
                        )
                    ],
                    force_provider=LLMProvider.PRIVATE,
                )
                assert result.content == "ok"


# ----------------------------------------------------------
# 响应模型校验
# ----------------------------------------------------------
class TestLLMResponse:
    def test_latency_ms_default(self) -> None:
        resp = LLMResponse(content="hi", model="m", provider=LLMProvider.KIMI)
        assert resp.latency_ms == 0.0

    def test_usage_optional(self) -> None:
        resp = LLMResponse(
            content="hi",
            model="m",
            provider=LLMProvider.KIMI,
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )
        assert resp.usage["prompt_tokens"] == 10
