# ============================================================
# 安全模块 — JWT 校验
# 实际 Token 由 auth-service 签发，各服务共享 secret 做校验
# ============================================================

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.logging import logger

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, str | list[str]]:
    """校验 JWT Token，解析并返回当前用户信息"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 20001, "message": "Token 无效或格式错误"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 20001, "message": "Token 已过期"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 20001, "message": "Token 无效或格式错误"},
        )

    return {
        "user_id": payload.get("sub", ""),
        "username": payload.get("username", ""),
        "roles": payload.get("roles", []),
        "permissions": payload.get("permissions", []),
    }
