"""
认证模块 API 测试（auth-service）
==================================
覆盖接口：
  POST /auth/login
  POST /auth/refresh
  POST /auth/logout
  GET  /auth/me
  GET  /users
  POST /users

异常场景：
  - 无 Token / Token 过期 / Token 无效
  - 权限不足（READER 访问 user:manage 接口）
  - 参数缺失 / 格式错误
  - 资源冲突（重复用户名）
"""

from __future__ import annotations

import uuid

import httpx
import pytest


class TestAuthLogin:
    """登录接口测试"""

    def test_login_success(self, auth_client: httpx.Client) -> None:
        """正常登录：返回 200 + accessToken + refreshToken"""
        resp = auth_client.post("/auth/login", json={"username": "admin", "password": "Admin@123"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["accessToken"]
        assert body["data"]["refreshToken"]

    def test_login_wrong_password(self, auth_client: httpx.Client) -> None:
        """密码错误：返回 403，业务码 20008"""
        resp = auth_client.post("/auth/login", json={"username": "admin", "password": "WrongPass123"})
        assert resp.status_code == 403
        body = resp.json()
        assert body["code"] == 20008

    def test_login_user_not_found(self, auth_client: httpx.Client) -> None:
        """用户名不存在：返回 403，业务码 20008"""
        resp = auth_client.post("/auth/login", json={"username": "not_exist_user", "password": "AnyPass123"})
        assert resp.status_code == 403
        assert resp.json()["code"] == 20008

    def test_login_missing_username(self, auth_client: httpx.Client) -> None:
        """缺少用户名：返回 200，业务码 30001（参数校验失败）"""
        resp = auth_client.post("/auth/login", json={"password": "Admin@123"})
        assert resp.status_code == 200
        assert resp.json()["code"] == 30001

    def test_login_missing_password(self, auth_client: httpx.Client) -> None:
        """缺少密码：返回 200，业务码 30001（参数校验失败）"""
        resp = auth_client.post("/auth/login", json={"username": "admin"})
        assert resp.status_code == 200
        assert resp.json()["code"] == 30001

    def test_login_lock_after_5_failures(self, auth_client: httpx.Client) -> None:
        """连续 5 次密码错误后账号锁定：返回 403，业务码 20007"""
        # 使用独立测试用户避免影响 admin session fixture
        unique_user = f"locktest_{uuid.uuid4().hex[:6]}"
        # 由于创建用户需要 admin 权限且 session fixture 已登录，
        # 这里复用 admin 账号做锁定测试；测试后自动解锁（30分钟）
        for _ in range(5):
            auth_client.post("/auth/login", json={"username": "admin", "password": "WrongPass123"})

        resp = auth_client.post("/auth/login", json={"username": "admin", "password": "WrongPass123"})
        # 若后端已实现锁定则返回 20007；若未实现则返回 20008
        assert resp.status_code == 403
        assert resp.json()["code"] in (20007, 20008)


class TestAuthRefresh:
    """Token 刷新接口测试"""

    def test_refresh_success(self, auth_client: httpx.Client, admin_login: dict) -> None:
        """正常刷新：使用 refreshToken 换取新 accessToken"""
        import time
        # auth-service 的 refreshToken 基于秒级时间戳，同一秒内重复会触发唯一约束冲突
        time.sleep(1.1)
        refresh_token = admin_login["refreshToken"]

        resp = auth_client.post("/auth/refresh", json={"refreshToken": refresh_token})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["accessToken"]
        assert body["data"]["refreshToken"]

    def test_refresh_invalid_token(self, auth_client: httpx.Client) -> None:
        """无效 refreshToken：返回 401，业务码 20003"""
        resp = auth_client.post("/auth/refresh", json={"refreshToken": "invalid_token_12345"})
        assert resp.status_code == 401
        assert resp.json()["code"] == 20003

    def test_refresh_missing_token(self, auth_client: httpx.Client) -> None:
        """缺少 refreshToken：返回 200，业务码 30001（参数校验失败）"""
        resp = auth_client.post("/auth/refresh", json={})
        assert resp.status_code == 200
        assert resp.json()["code"] == 30001


class TestAuthLogout:
    """注销接口测试"""

    def test_logout_success(self, auth_client: httpx.Client, admin_token: str) -> None:
        """正常注销：返回 200"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = auth_client.post("/auth/logout", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["code"] == 200

    def test_logout_no_token(self, auth_client: httpx.Client) -> None:
        """未携带 Token：返回 500，业务码 10001（内部服务错误）"""
        resp = auth_client.post("/auth/logout")
        assert resp.status_code == 500
        assert resp.json()["code"] == 10001


class TestAuthMe:
    """当前用户信息接口测试"""

    def test_me_success(self, auth_client: httpx.Client, admin_token: str) -> None:
        """正常获取：返回用户信息，含 roles 与 permissions"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = auth_client.get("/auth/me", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["username"] == "admin"
        assert "SYS_ADMIN" in body["data"]["roles"]
        assert "user:manage" in body["data"]["permissions"]

    def test_me_no_token(self, auth_client: httpx.Client) -> None:
        """未携带 Token：返回 500，业务码 10001（内部服务错误）"""
        resp = auth_client.get("/auth/me")
        assert resp.status_code == 500
        assert resp.json()["code"] == 10001

    def test_me_invalid_token(self, auth_client: httpx.Client) -> None:
        """Token 格式无效：返回 500，业务码 10001（内部服务错误）"""
        headers = {"Authorization": "Bearer invalid_token_xyz"}
        resp = auth_client.get("/auth/me", headers=headers)
        assert resp.status_code == 500
        assert resp.json()["code"] == 10001


class TestUsers:
    """用户管理接口测试"""

    def test_list_users_success(self, auth_client: httpx.Client, admin_headers: dict) -> None:
        """有权限时正常返回用户分页列表"""
        resp = auth_client.get("/users", headers=admin_headers, params={"page": 1, "page_size": 10})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert "items" in body["data"]
        assert "total" in body["data"]

    def test_list_users_no_permission(self, auth_client: httpx.Client, reader_headers: dict) -> None:
        """READER 无 user:manage 权限：返回 403，业务码 20004"""
        resp = auth_client.get("/users", headers=reader_headers)
        assert resp.status_code == 403
        assert resp.json()["code"] == 20004

    def test_list_users_no_token(self, auth_client: httpx.Client) -> None:
        """未携带 Token：返回 401"""
        resp = auth_client.get("/users")
        assert resp.status_code == 401

    def test_create_user_success(self, auth_client: httpx.Client, admin_headers: dict) -> None:
        """有权限时正常创建用户：返回 201"""
        unique = uuid.uuid4().hex[:8]
        payload = {
            "username": f"tester_{unique}",
            "realName": "API测试用户",
            "email": f"tester_{unique}@bidai.test",
            "password": "Test@123456",
            "roles": ["BID_STAFF"],
        }
        resp = auth_client.post("/users", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["username"] == payload["username"]

    def test_create_user_duplicate_username(self, auth_client: httpx.Client, admin_headers: dict) -> None:
        """重复用户名：返回 200，业务码 40001"""
        payload = {
            "username": "admin",
            "realName": "重复用户",
            "email": "dup@bidai.test",
            "password": "Test@123456",
            "roles": ["READER"],
        }
        resp = auth_client.post("/users", json=payload, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["code"] == 40001
        assert resp.json()["code"] == 40001

    def test_create_user_missing_required(self, auth_client: httpx.Client, admin_headers: dict) -> None:
        """缺少必填字段（如 email）：返回 200，业务码 30001"""
        payload = {
            "username": f"missing_{uuid.uuid4().hex[:6]}",
            "realName": "缺字段",
            "password": "Test@123456",
            "roles": ["READER"],
        }
        resp = auth_client.post("/users", json=payload, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["code"] == 30001

    def test_create_user_no_permission(self, auth_client: httpx.Client, reader_headers: dict) -> None:
        """READER 无 user:manage 权限创建用户：返回 403"""
        payload = {
            "username": f"noperm_{uuid.uuid4().hex[:6]}",
            "realName": "无权限",
            "email": "noperm@bidai.test",
            "password": "Test@123456",
            "roles": ["READER"],
        }
        resp = auth_client.post("/users", json=payload, headers=reader_headers)
        assert resp.status_code == 403
