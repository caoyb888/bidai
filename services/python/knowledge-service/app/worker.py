# ============================================================
# Celery Worker 配置
# 耗时操作（OCR、LLM 生成）必须通过任务队列异步处理
# ============================================================

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    settings.app_name,
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.ai.tasks"],  # AI 任务模块
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 分钟硬限制
    task_soft_time_limit=300,  # 5 分钟软限制
    worker_prefetch_multiplier=1,  # 公平调度，避免长任务阻塞
)
