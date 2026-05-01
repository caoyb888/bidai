# ============================================================
# 健康检查单元测试
# 验收标准：/health 返回 200
# ============================================================

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["message"] == "healthy"
