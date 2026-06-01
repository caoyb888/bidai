# ============================================================
# 统一 LLM 调用客户端 — 支持私有化 vLLM / Kimi / DeepSeek
# 降级链：私有模型 → Kimi → DeepSeek → 错误
# 符合 CLAUDE.md §7.2 LLM 调用规范
# ============================================================

from __future__ import annotations

import re
import time
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import logger


class LLMProvider(str, Enum):
    PRIVATE = "private"  # 私有化 vLLM / Ollama
    KIMI = "kimi"  # Moonshot AI
    DEEPSEEK = "deepseek"  # DeepSeek


class ChatMessage(BaseModel):
    role: str
    content: str


class LLMResponse(BaseModel):
    content: str
    model: str
    provider: LLMProvider
    usage: dict[str, int] | None = None
    latency_ms: float = 0.0


class LLMTimeoutError(Exception):
    """LLM 请求超时"""


class LLMAPIError(Exception):
    """LLM API 调用异常"""


class SensitiveDataViolationError(Exception):
    """检测到敏感数据，禁止发送至外部 LLM API"""


class SensitiveDataGuard:
    """敏感数据检测守卫 — 符合 CLAUDE.md §9.3"""

    SENSITIVE_PATTERNS: list[str] = [
        r"\d{18}",  # 身份证号
        r"1[3-9]\d{9}",  # 手机号
        r"\d{6,}元",  # 金额（明文）
    ]

    @classmethod
    def check(cls, text: str, target_provider: LLMProvider) -> None:
        if target_provider == LLMProvider.PRIVATE:
            return
        for pattern in cls.SENSITIVE_PATTERNS:
            if re.search(pattern, text):
                raise SensitiveDataViolationError(
                    "检测到敏感数据，禁止发送至外部 LLM API"
                )


class LLMClient:
    """
    统一 LLM 调用客户端

    自动按降级链选择可用 provider：
        私有化模型 → Kimi → DeepSeek → 报错
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=120.0)
        self._providers: list[LLMProvider] = []
        self._init_providers()

    def _init_providers(self) -> None:
        if settings.llm_private_base_url and settings.llm_private_model:
            self._providers.append(LLMProvider.PRIVATE)

        if settings.llm_kimi_api_key:
            self._providers.append(LLMProvider.KIMI)

        if settings.llm_deepseek_api_key:
            self._providers.append(LLMProvider.DEEPSEEK)

        logger.info(
            "llm_providers_initialized",
            extra={"providers": [p.value for p in self._providers]},
        )

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        force_provider: LLMProvider | None = None,
    ) -> LLMResponse:
        """
        统一聊天接口，自动按降级链选择可用 provider。

        Args:
            messages: 对话消息列表
            model: 指定模型名（None 则使用 provider 默认模型）
            temperature: 采样温度
            max_tokens: 最大生成 token 数
            force_provider: 强制使用指定 provider（用于测试或敏感内容控制）

        Returns:
            LLMResponse: 包含生成内容、模型信息、延迟等

        Raises:
            LLMAPIError: 所有 provider 均不可用
            LLMTimeoutError: 请求超时
            SensitiveDataViolationError: 检测到敏感数据发往外部 API
        """
        providers = [force_provider] if force_provider else self._providers

        if not providers:
            raise LLMAPIError("没有可用的 LLM Provider，请检查环境变量配置")

        last_error: Exception | None = None

        for provider in providers:
            try:
                return await self._chat_single(
                    provider=provider,
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except (LLMTimeoutError, LLMAPIError) as e:
                last_error = e
                logger.warning(
                    "llm_provider_failed",
                    extra={"provider": provider.value, "error": str(e)},
                )
                continue

        raise LLMAPIError(
            f"所有 LLM Provider 均不可用，最后一个错误: {last_error}"
        )

    async def _chat_single(
        self,
        provider: LLMProvider,
        messages: list[ChatMessage],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        # 敏感数据检测（外部 API 场景）
        text = "".join(m.content for m in messages)
        SensitiveDataGuard.check(text, provider)

        start = time.perf_counter()

        if provider == LLMProvider.PRIVATE:
            resp = await self._call_private(
                messages, model, temperature, max_tokens
            )
        elif provider == LLMProvider.KIMI:
            resp = await self._call_kimi(
                messages, model, temperature, max_tokens
            )
        elif provider == LLMProvider.DEEPSEEK:
            resp = await self._call_deepseek(
                messages, model, temperature, max_tokens
            )
        else:
            raise LLMAPIError(f"未知 Provider: {provider}")

        latency_ms = (time.perf_counter() - start) * 1000
        resp.latency_ms = latency_ms

        logger.info(
            "llm_chat_success",
            extra={
                "provider": provider.value,
                "model": resp.model,
                "latency_ms": round(latency_ms, 2),
                "tokens": resp.usage,
            },
        )

        return resp

    async def _call_private(
        self,
        messages: list[ChatMessage],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        base_url = settings.llm_private_base_url.rstrip("/")
        url = f"{base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": model or settings.llm_private_model,
            "messages": [m.model_dump() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            r = await self._client.post(
                url,
                json=payload,
                timeout=settings.llm_private_timeout,
            )
            r.raise_for_status()
            data = r.json()
        except httpx.TimeoutException as e:
            raise LLMTimeoutError("私有化 LLM 请求超时") from e
        except httpx.HTTPStatusError as e:
            raise LLMAPIError(
                f"私有化 LLM API 错误: {e.response.status_code}"
            ) from e

        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model", model or settings.llm_private_model),
            provider=LLMProvider.PRIVATE,
            usage=data.get("usage"),
        )

    async def _call_kimi(
        self,
        messages: list[ChatMessage],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        url = "https://api.moonshot.cn/v1/chat/completions"
        payload: dict[str, Any] = {
            "model": model or settings.llm_kimi_model,
            "messages": [m.model_dump() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            r = await self._client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.llm_kimi_api_key}"
                },
                timeout=settings.llm_kimi_timeout,
            )
            r.raise_for_status()
            data = r.json()
        except httpx.TimeoutException as e:
            raise LLMTimeoutError("Kimi API 请求超时") from e
        except httpx.HTTPStatusError as e:
            raise LLMAPIError(
                f"Kimi API 错误: {e.response.status_code} {e.response.text}"
            ) from e

        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model", model or settings.llm_kimi_model),
            provider=LLMProvider.KIMI,
            usage=data.get("usage"),
        )

    async def _call_deepseek(
        self,
        messages: list[ChatMessage],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        url = "https://api.deepseek.com/v1/chat/completions"
        payload: dict[str, Any] = {
            "model": model or settings.llm_deepseek_model,
            "messages": [m.model_dump() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            r = await self._client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.llm_deepseek_api_key}"
                },
                timeout=settings.llm_deepseek_timeout,
            )
            r.raise_for_status()
            data = r.json()
        except httpx.TimeoutException as e:
            raise LLMTimeoutError("DeepSeek API 请求超时") from e
        except httpx.HTTPStatusError as e:
            raise LLMAPIError(
                f"DeepSeek API 错误: {e.response.status_code} {e.response.text}"
            ) from e

        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model", model or settings.llm_deepseek_model),
            provider=LLMProvider.DEEPSEEK,
            usage=data.get("usage"),
        )

    async def close(self) -> None:
        await self._client.aclose()


# 全局单例（按需使用，建议在应用生命周期内管理）
llm_client = LLMClient()
