"""
BidAI API 测试共享配置与 Fixture
==================================
提供：
- 两个服务的 httpx Client
- Admin Token（全权限）
- Reader Token（仅 project:read / report:read，用于权限不足测试）
"""

from __future__ import annotations

import time
import uuid
from typing import Generator

import httpx
import pytest

# ----------------------------------------------------------
# 服务端点配置（对齐 docker-compose.dev.yml 与 application.yml）
# ----------------------------------------------------------
BASE_URL_AUTH = "http://localhost:8081/api/v1"
BASE_URL_PROJECT = "http://localhost:8082/api/v1"

# 预置管理员账号（见 V2__seed_roles_and_admin.sql）
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="session")
def auth_client() -> Generator[httpx.Client, None, None]:
    """auth-service 长连接客户端"""
    transport = httpx.HTTPTransport(retries=0)
    with httpx.Client(base_url=BASE_URL_AUTH, timeout=30.0, transport=transport) as client:
        yield client


@pytest.fixture(scope="session")
def project_client() -> Generator[httpx.Client, None, None]:
    """project-service 长连接客户端"""
    transport = httpx.HTTPTransport(retries=0)
    with httpx.Client(base_url=BASE_URL_PROJECT, timeout=30.0, transport=transport) as client:
        yield client


def _do_login(client: httpx.Client, username: str, password: str) -> dict:
    """登录并返回完整 data 字段；若因秒级重复 token 导致 500，则等待 1s 后重试。"""
    resp = client.post("/auth/login", json={"username": username, "password": password})
    if resp.status_code == 500 and "uq_refresh_tokens_hash" in resp.text:
        time.sleep(1.1)
        resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"登录失败 ({username}): {resp.text}"
    data = resp.json()["data"]
    assert "accessToken" in data
    return data


@pytest.fixture(scope="session")
def admin_login(auth_client: httpx.Client) -> dict:
    """管理员登录并返回完整登录响应数据（含 accessToken / refreshToken）"""
    return _do_login(auth_client, ADMIN_USERNAME, ADMIN_PASSWORD)


@pytest.fixture(scope="session")
def admin_token(admin_login: dict) -> str:
    """管理员 access_token"""
    return admin_login["accessToken"]


@pytest.fixture(scope="session")
def reader_user(auth_client: httpx.Client, admin_token: str) -> dict:
    """
    创建一个 READER 角色的测试用户（仅 project:read / report:read）。
    用于验证权限不足的异常场景。
    """
    unique = uuid.uuid4().hex[:8]
    username = f"reader_{unique}"
    payload = {
        "username": username,
        "realName": "测试只读用户",
        "email": f"{username}@bidai.test",
        "password": "Reader@123",
        "roles": ["READER"],
    }

    headers = {"Authorization": f"Bearer {admin_token}"}
    create_resp = auth_client.post("/users", json=payload, headers=headers)

    if create_resp.status_code == 409:
        # 用户已存在，查询并复用
        list_resp = auth_client.get("/users", headers=headers, params={"keyword": username})
        assert list_resp.status_code == 200
        items = list_resp.json()["data"]["items"]
        user = items[0]
    else:
        assert create_resp.status_code == 201, f"创建 Reader 用户失败: {create_resp.text}"
        user = create_resp.json()["data"]

    return {"username": username, "password": "Reader@123", "id": user["id"]}


@pytest.fixture(scope="session")
def reader_token(auth_client: httpx.Client, reader_user: dict) -> str:
    """READER 用户登录并返回 access_token"""
    resp = auth_client.post("/auth/login", json={"username": reader_user["username"], "password": reader_user["password"]})
    assert resp.status_code == 200, f"Reader 登录失败: {resp.text}"
    return resp.json()["data"]["accessToken"]


@pytest.fixture(scope="session")
def admin_headers(admin_token: str) -> dict:
    """带管理员 Token 的请求头"""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def reader_headers(reader_token: str) -> dict:
    """带 Reader Token 的请求头"""
    return {"Authorization": f"Bearer {reader_token}"}
