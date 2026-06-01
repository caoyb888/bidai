# ============================================================
# 单元测试：ES 索引补偿任务（sync_tasks）
# ============================================================

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.ai.sync_tasks import _compensate_es_index, es_index_compensate_task
from app.models.kb_document import KbDocument


class TestCompensateEsIndex:
    """_compensate_es_index 单元测试"""

    @patch("app.ai.sync_tasks.AsyncSessionLocal")
    async def test_no_unindexed_docs(
        self,
        mock_session_cls: MagicMock,
    ) -> None:
        """测试无待补偿文档时返回空结果"""
        mock_kb_repo = MagicMock()
        mock_kb_repo.get_unindexed_documents = AsyncMock(return_value=[])

        mock_session = MagicMock()
        mock_session_cls.return_value = MagicMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=None),
        )

        with patch(
            "app.ai.sync_tasks.KnowledgeRepository", return_value=mock_kb_repo
        ):
            result = await _compensate_es_index()

        assert result["compensated"] == 0
        assert result["failed"] == 0
        assert result["doc_ids"] == []
        mock_kb_repo.get_unindexed_documents.assert_awaited_once_with(limit=50)

    @patch("app.ai.sync_tasks.sync_document_to_es")
    @patch("app.ai.sync_tasks.AsyncSessionLocal")
    async def test_compensate_all_success(
        self,
        mock_session_cls: MagicMock,
        mock_sync_es: AsyncMock,
    ) -> None:
        """测试全部补偿成功"""
        doc1 = MagicMock(spec=KbDocument)
        doc1.id = uuid4()
        doc2 = MagicMock(spec=KbDocument)
        doc2.id = uuid4()

        mock_kb_repo = MagicMock()
        mock_kb_repo.get_unindexed_documents = AsyncMock(return_value=[doc1, doc2])

        mock_session = MagicMock()
        mock_session_cls.return_value = MagicMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=None),
        )

        mock_sync_es.return_value = True

        with patch(
            "app.ai.sync_tasks.KnowledgeRepository", return_value=mock_kb_repo
        ):
            result = await _compensate_es_index()

        assert result["compensated"] == 2
        assert result["failed"] == 0
        assert len(result["doc_ids"]) == 2
        assert mock_sync_es.call_count == 2

    @patch("app.ai.sync_tasks.sync_document_to_es")
    @patch("app.ai.sync_tasks.AsyncSessionLocal")
    async def test_compensate_partial_failure(
        self,
        mock_session_cls: MagicMock,
        mock_sync_es: AsyncMock,
    ) -> None:
        """测试部分补偿失败"""
        doc1 = MagicMock(spec=KbDocument)
        doc1.id = uuid4()
        doc2 = MagicMock(spec=KbDocument)
        doc2.id = uuid4()

        mock_kb_repo = MagicMock()
        mock_kb_repo.get_unindexed_documents = AsyncMock(return_value=[doc1, doc2])

        mock_session = MagicMock()
        mock_session_cls.return_value = MagicMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=None),
        )

        mock_sync_es.side_effect = [True, False]

        with patch(
            "app.ai.sync_tasks.KnowledgeRepository", return_value=mock_kb_repo
        ):
            result = await _compensate_es_index()

        assert result["compensated"] == 1
        assert result["failed"] == 1
        assert result["doc_ids"] == [str(doc1.id)]


class TestEsIndexCompensateTask:
    """es_index_compensate_task Celery 任务测试"""

    @patch("app.ai.sync_tasks.asyncio.run")
    def test_task_success(self, mock_run: MagicMock) -> None:
        """测试补偿任务正常执行（直接调用 run 绕过 Celery 代理层）"""
        mock_run.return_value = {
            "compensated": 3,
            "failed": 0,
            "doc_ids": ["d1", "d2", "d3"],
        }

        result = es_index_compensate_task.run()

        assert result["compensated"] == 3
        assert result["failed"] == 0
        mock_run.assert_called_once()

    @patch("app.ai.sync_tasks.asyncio.run")
    def test_task_retry_on_failure(self, mock_run: MagicMock) -> None:
        """测试任务失败时触发重试"""
        mock_run.side_effect = RuntimeError("db connection lost")

        with patch.object(es_index_compensate_task, "retry") as mock_retry:
            mock_retry.side_effect = Exception("retry triggered")
            with pytest.raises(Exception, match="retry triggered"):
                es_index_compensate_task.run()

        mock_run.assert_called_once()
        mock_retry.assert_called_once()
