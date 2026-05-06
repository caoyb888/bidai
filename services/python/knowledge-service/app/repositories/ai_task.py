# ============================================================
# AI 任务数据访问层 — Repository
# ============================================================

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_task import AiTask


class AiTaskRepository:
    """AI 任务 Repository"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        task_type: str,
        ref_type: str | None,
        ref_id: UUID | None,
        celery_task_id: str,
        input_payload: dict[str, Any],
        created_by: str,
    ) -> AiTask:
        """创建 AI 任务记录"""
        now = datetime.now(UTC)
        task = AiTask(
            task_type=task_type,
            task_status="PENDING",
            priority=5,
            ref_type=ref_type,
            ref_id=ref_id,
            celery_task_id=celery_task_id,
            queue_name="default",
            input_payload=input_payload,
            max_retries=3,
            queued_at=now,
            created_at=now,
            created_by=created_by,
        )
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def get_by_ref(self, ref_type: str, ref_id: str) -> AiTask | None:
        """根据关联实体查询最新任务"""
        stmt = (
            select(AiTask)
            .where(
                AiTask.ref_type == ref_type,
                AiTask.ref_id == UUID(ref_id),
            )
            .order_by(AiTask.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        task_id: UUID,
        *,
        task_status: str,
        result_payload: dict[str, Any] | None = None,
        error_message: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """更新任务状态"""
        task = await self.session.get(AiTask, task_id)
        if task is None:
            return

        task.task_status = task_status  # type: ignore[assignment]
        now = datetime.now(UTC)
        if task_status == "RUNNING" and task.started_at is None:
            task.started_at = now
        if task_status in ("SUCCESS", "FAILED"):
            task.completed_at = now  # type: ignore[assignment]
            if task.started_at is not None:
                task.duration_ms = int((now - task.started_at).total_seconds() * 1000)  # type: ignore[assignment]
        if result_payload is not None:
            task.result_payload = result_payload  # type: ignore[assignment]
        if error_message is not None:
            task.error_message = error_message  # type: ignore[assignment]
        if duration_ms is not None:
            task.duration_ms = duration_ms  # type: ignore[assignment]
        await self.session.flush()
