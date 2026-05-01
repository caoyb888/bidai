# ============================================================
# 安全模块 — JWT 校验占位
# 实际 Token 由 auth-service 签发，各服务只做校验
# ============================================================

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, str | list[str]]:
    """校验 JWT Token，返回当前用户信息占位"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 20001, "message": "Token 无效或格式错误"},
        )
    # TODO: 接入 auth-service 公钥验证（S1-1 完成后替换）
    return {"user_id": "stub_user", "roles": ["BID_STAFF"]}
