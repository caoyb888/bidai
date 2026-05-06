# ============================================================
# 健康检查接口
# 验收标准：/health 返回 200
# ============================================================

from fastapi import APIRouter, status

from app.schemas.base import CommonResponse

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK, response_model=CommonResponse[dict[str, str]])
async def health_check() -> CommonResponse[dict[str, str]]:
    return CommonResponse[dict[str, str]](code=200, message="healthy", data={"service": "knowledge-service"})
