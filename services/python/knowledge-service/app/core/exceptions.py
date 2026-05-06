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
        self.message = message
        self.biz_detail = detail
        super().__init__(
            status_code=status_code,
            detail={
                "code": code,
                "message": message,
                "detail": detail,
            },
        )


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


class InvalidFileTypeError(BaseServiceException):
    """文件类型不在白名单（错误码 30004）"""

    def __init__(self, ext: str) -> None:
        super().__init__(
            code=30004,
            message="文件类型不在白名单",
            detail=f"仅支持 pdf/docx/xlsx/jpg/png，当前后缀: {ext}",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class FileTooLargeError(BaseServiceException):
    """文件大小超过限制（错误码 30005）"""

    def __init__(self, size_mb: float, max_mb: int) -> None:
        super().__init__(
            code=30005,
            message="文件大小超过限制",
            detail=f"当前大小: {size_mb:.2f}MB，最大允许: {max_mb}MB",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class DuplicateFileError(BaseServiceException):
    """知识库文档哈希重复，文件已存在（错误码 40008）"""

    def __init__(self, document_id: str) -> None:
        super().__init__(
            code=40008,
            message="知识库文档哈希重复，文件已存在",
            detail=f"document_id={document_id}",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class StorageError(BaseServiceException):
    """文件存储服务异常（错误码 10003）"""

    def __init__(self, message: str = "文件存储服务异常") -> None:
        super().__init__(
            code=10003,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
