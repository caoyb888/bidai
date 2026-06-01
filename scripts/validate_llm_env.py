#!/usr/bin/env python3
# ============================================================
# S0-009 · 私有化 LLM 环境验证脚本
# ============================================================
# 当前阶段（无 GPU）：验证外部 API 降级链路（Kimi / DeepSeek）
# 用法:
#   cd /path/to/bid-ai-system
#   # 配置 API Key 后执行
#   export LLM_KIMI_API_KEY=sk-xxx
#   export LLM_DEEPSEEK_API_KEY=sk-yyy
#   python3 scripts/validate_llm_env.py
#
#   # 或使用知识库服务的 venv
#   services/python/knowledge-service/.venv/bin/python scripts/validate_llm_env.py
# ============================================================

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

# 优先使用 knowledge-service 的依赖（httpx）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "python", "knowledge-service"))

try:
    import httpx
except ImportError:
    print("ERROR: 缺少 httpx，请安装依赖: pip install httpx")
    print("提示: 可使用 knowledge-service 的虚拟环境:")
    print("  services/python/knowledge-service/.venv/bin/python scripts/validate_llm_env.py")
    sys.exit(1)


# ----------------------------------------------------------
# 配置
# ----------------------------------------------------------
KIMI_BASE_URL = "https://api.moonshot.cn/v1"
KIMI_MODEL = os.getenv("LLM_KIMI_MODEL", "moonshot-v1-8k")
KIMI_API_KEY = os.getenv("LLM_KIMI_API_KEY", "")
KIMI_TIMEOUT = int(os.getenv("LLM_KIMI_TIMEOUT", "60"))

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = os.getenv("LLM_DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_API_KEY = os.getenv("LLM_DEEPSEEK_API_KEY", "")
DEEPSEEK_TIMEOUT = int(os.getenv("LLM_DEEPSEEK_TIMEOUT", "60"))

# S0-009 验收标准：平均响应 < 10s
MAX_ACCEPTABLE_LATENCY_MS = 10_000

# 投标场景测试 Prompt（验证 AI 对业务场景的理解能力）
TEST_PROMPTS = [
    {
        "name": "基础连通性",
        "messages": [
            {"role": "user", "content": "请用一句话介绍你自己。"}
        ],
        "assert_contains": None,
    },
    {
        "name": "约束提取能力",
        "messages": [
            {
                "role": "system",
                "content": "你是一位资深投标专家，擅长从招标文件中提取关键约束条件。",
            },
            {
                "role": "user",
                "content": (
                    "请从以下招标文件片段中提取约束条件，并说明是否为废标条款：\n\n"
                    "'投标人须具备建筑工程施工总承包一级及以上资质，"
                    "注册资本不低于5000万元，近三年内无重大违法记录。"
                    "投标文件须加盖公章并由法定代表人签字。'"
                ),
            },
        ],
        "assert_contains": "资质",
    },
    {
        "name": "JSON 结构化输出",
        "messages": [
            {
                "role": "system",
                "content": "你是一个结构化的信息提取助手，输出必须是合法的 JSON。",
            },
            {
                "role": "user",
                "content": (
                    "请提取以下信息并以 JSON 输出：\n"
                    "项目名称：智慧城市数据中心建设项目\n"
                    "预算金额：1200万元\n"
                    "工期要求：180日历天\n"
                    "输出格式：{\"project_name\": \"...\", \"budget\": ..., \"duration\": \"...\"}"
                ),
            },
        ],
        "assert_contains": "智慧城市",
    },
]


# ----------------------------------------------------------
# 数据模型
# ----------------------------------------------------------
@dataclass
class ProviderResult:
    name: str
    available: bool = False
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    tests_passed: int = 0
    tests_failed: int = 0
    errors: list[str] = field(default_factory=list)
    details: list[dict[str, Any]] = field(default_factory=list)


# ----------------------------------------------------------
# API 调用
# ----------------------------------------------------------
async def call_chat_completions(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    timeout: int,
) -> dict[str, Any]:
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1024,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    start = time.perf_counter()
    resp = await client.post(url, json=payload, headers=headers, timeout=timeout)
    latency_ms = (time.perf_counter() - start) * 1000

    resp.raise_for_status()
    data = resp.json()

    return {
        "content": data["choices"][0]["message"]["content"],
        "model": data.get("model", model),
        "usage": data.get("usage"),
        "latency_ms": latency_ms,
    }


# ----------------------------------------------------------
# 单 Provider 验证
# ----------------------------------------------------------
async def validate_provider(
    client: httpx.AsyncClient,
    name: str,
    base_url: str,
    api_key: str,
    model: str,
    timeout: int,
) -> ProviderResult:
    result = ProviderResult(name=name)

    if not api_key:
        result.errors.append(f"环境变量未配置（{name.upper()}_API_KEY）")
        return result

    latencies: list[float] = []

    for test in TEST_PROMPTS:
        detail: dict[str, Any] = {
            "test_name": test["name"],
            "passed": False,
            "latency_ms": 0.0,
            "error": None,
            "response_snippet": "",
        }

        try:
            resp = await call_chat_completions(
                client, base_url, api_key, model, test["messages"], timeout
            )
            detail["latency_ms"] = resp["latency_ms"]
            detail["response_snippet"] = resp["content"][:200].replace("\n", " ")
            latencies.append(resp["latency_ms"])

            # 断言：响应时间 < 10s
            if resp["latency_ms"] > MAX_ACCEPTABLE_LATENCY_MS:
                detail["error"] = (
                    f"响应超时: {resp['latency_ms']:.0f}ms > "
                    f"{MAX_ACCEPTABLE_LATENCY_MS}ms"
                )
                result.tests_failed += 1
            else:
                # 断言：内容包含期望字符串
                expected = test.get("assert_contains")
                if expected and expected not in resp["content"]:
                    detail["error"] = f"响应内容未包含期望文本: '{expected}'"
                    result.tests_failed += 1
                else:
                    detail["passed"] = True
                    result.tests_passed += 1

        except httpx.TimeoutException:
            detail["error"] = f"请求超时（>{timeout}s）"
            result.tests_failed += 1
            result.errors.append(f"{test['name']}: 请求超时")
        except httpx.HTTPStatusError as e:
            detail["error"] = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            result.tests_failed += 1
            result.errors.append(f"{test['name']}: HTTP {e.response.status_code}")
        except Exception as e:
            detail["error"] = f"异常: {e}"
            result.tests_failed += 1
            result.errors.append(f"{test['name']}: {e}")

        result.details.append(detail)

    if latencies:
        result.avg_latency_ms = sum(latencies) / len(latencies)
        result.max_latency_ms = max(latencies)
        result.available = True

    return result


# ----------------------------------------------------------
# 降级链路验证
# ----------------------------------------------------------
def validate_fallback_chain(
    kimi_result: ProviderResult,
    deepseek_result: ProviderResult,
) -> dict[str, Any]:
    """验证降级链路：至少一个外部 Provider 可用时，系统可正常运行"""
    fallback_ok = kimi_result.available or deepseek_result.available
    return {
        "fallback_ok": fallback_ok,
        "primary": "kimi" if kimi_result.available else "deepseek",
        "backup": "deepseek" if not deepseek_result.available else "kimi",
        "note": (
            "通过" if fallback_ok else "失败：Kimi 和 DeepSeek 均不可用"
        ),
    }


# ----------------------------------------------------------
# 报告输出
# ----------------------------------------------------------
def print_report(
    kimi: ProviderResult,
    deepseek: ProviderResult,
    fallback: dict[str, Any],
) -> None:
    print("=" * 70)
    print("S0-009 · 私有化 LLM 环境验证报告")
    print("=" * 70)
    print()
    print("【当前阶段】无 GPU 节点，使用公网 API 作为降级备用验证")
    print("【验收标准】/v1/chat/completions 可调用 | 平均响应 < 10s | Prompt 正确响应")
    print()

    providers = [kimi, deepseek]
    for p in providers:
        status = "✅ 可用" if p.available else "❌ 不可用"
        print(f"--- {p.name} {status} ---")
        if not p.available:
            for err in p.errors:
                print(f"  错误: {err}")
            print()
            continue

        print(f"  平均响应: {p.avg_latency_ms:.0f}ms")
        print(f"  最大响应: {p.max_latency_ms:.0f}ms")
        print(f"  通过测试: {p.tests_passed}/{p.tests_passed + p.tests_failed}")
        for d in p.details:
            icon = "✅" if d["passed"] else "❌"
            print(f"    {icon} {d['test_name']} ({d['latency_ms']:.0f}ms)")
            if d["error"]:
                print(f"       错误: {d['error']}")
            print(f"       响应: {d['response_snippet'][:120]}...")
        print()

    print("--- 降级链路验证 ---")
    print(f"  降级可用: {'✅ 通过' if fallback['fallback_ok'] else '❌ 失败'}")
    print(f"  说明: {fallback['note']}")
    print()

    # 汇总判定
    all_pass = any(p.available for p in providers) and fallback["fallback_ok"]
    # 进一步检查：可用 provider 的平均响应是否 < 10s
    for p in providers:
        if p.available and p.avg_latency_ms > MAX_ACCEPTABLE_LATENCY_MS:
            all_pass = False
            print(f"⚠️  {p.name} 平均响应 {p.avg_latency_ms:.0f}ms 超过阈值 {MAX_ACCEPTABLE_LATENCY_MS}ms")

    print("=" * 70)
    if all_pass:
        print("🎉 验证结果: 通过（至少一个外部 LLM API 可用且响应达标）")
    else:
        print("⚠️  验证结果: 未通过")
        print()
        print("请检查以下配置后重试:")
        print("  export LLM_KIMI_API_KEY=sk-your-kimi-key")
        print("  export LLM_DEEPSEEK_API_KEY=sk-your-deepseek-key")
    print("=" * 70)


def print_json_report(
    kimi: ProviderResult,
    deepseek: ProviderResult,
    fallback: dict[str, Any],
) -> None:
    report = {
        "story_id": "S0-009",
        "story_name": "私有化 LLM 环境验证",
        "phase": "external_api_fallback_verification",
        "providers": [
            {
                "name": p.name,
                "available": p.available,
                "avg_latency_ms": round(p.avg_latency_ms, 2),
                "max_latency_ms": round(p.max_latency_ms, 2),
                "tests_passed": p.tests_passed,
                "tests_failed": p.tests_failed,
                "errors": p.errors,
            }
            for p in [kimi, deepseek]
        ],
        "fallback": fallback,
        "criteria": {
            "endpoint_callable": any(p.available for p in [kimi, deepseek]),
            "avg_latency_under_10s": all(
                p.avg_latency_ms <= MAX_ACCEPTABLE_LATENCY_MS
                for p in [kimi, deepseek]
                if p.available
            ),
            "prompt_response_correct": all(
                p.tests_passed > 0
                for p in [kimi, deepseek]
                if p.available
            ),
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


# ----------------------------------------------------------
# 主入口
# ----------------------------------------------------------
async def main() -> int:
    print("S0-009 LLM 环境验证开始...\n")

    async with httpx.AsyncClient() as client:
        kimi = await validate_provider(
            client,
            "Kimi (Moonshot)",
            KIMI_BASE_URL,
            KIMI_API_KEY,
            KIMI_MODEL,
            KIMI_TIMEOUT,
        )
        deepseek = await validate_provider(
            client,
            "DeepSeek",
            DEEPSEEK_BASE_URL,
            DEEPSEEK_API_KEY,
            DEEPSEEK_MODEL,
            DEEPSEEK_TIMEOUT,
        )

    fallback = validate_fallback_chain(kimi, deepseek)

    # 输出格式选择
    if "--json" in sys.argv:
        print_json_report(kimi, deepseek, fallback)
    else:
        print_report(kimi, deepseek, fallback)

    # 返回退出码
    all_pass = any(p.available for p in [kimi, deepseek]) and fallback["fallback_ok"]
    for p in [kimi, deepseek]:
        if p.available and p.avg_latency_ms > MAX_ACCEPTABLE_LATENCY_MS:
            all_pass = False
    return 0 if all_pass else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
