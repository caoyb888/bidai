# ============================================================
# 统一异常体系 — 与 API Spec 错误码对齐
# ============================================================

from fastapi import HTTPException, status


class BaseServiceException(HTTPException):
    """业务异常基类"""

    def __init__(
        self,
        code: int,
        message: str,
        detail: str | None = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        self.biz_code = code
        super().__init__(status_code=status_code, detail={
            "code": code,
            "message": message,
            "detail": detail,
        })


class NotFoundError(BaseServiceException):
    def __init__(self, resource: str = "资源") -> None:
        super().__init__(
            code=40002,
            message=f"{resource}不存在或已删除",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ForbiddenError(BaseServiceException):
    def __init__(self, message: str = "权限不足，无法执行此操作") -> None:
        super().__init__(
            code=20004,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ServiceUnavailableError(BaseServiceException):
    def __init__(self, message: str = "服务暂不可用，请稍后重试") -> None:
        super().__init__(
            code=10004,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class InternalServerError(BaseServiceException):
    def __init__(self, message: str = "内部服务错误") -> None:
        super().__init__(
            code=10001,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
