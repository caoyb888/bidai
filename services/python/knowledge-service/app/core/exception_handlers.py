# ============================================================
# 全局异常处理器 — 统一响应格式
# ============================================================

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import BaseServiceException


async def base_service_exception_handler(
    request: Request,
    exc: BaseServiceException,
) -> JSONResponse:
    """处理所有业务异常，返回统一格式"""
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.biz_code,
            "message": exc.message,
            "detail": exc.detail if settings.debug else None,
            "request_id": request_id,
        },
    )
