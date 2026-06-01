# ============================================================
# 单元测试：KnowledgeService.get_stats（S1-2-006）
# ============================================================

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.kb_document import KbDocument
from app.schemas.base import KnowledgeStatsResponse
from app.services.knowledge import KnowledgeService


def _make_kb_document(**kwargs: object) -> KbDocument:
    """构造 KbDocument ORM 对象"""
    doc = KbDocument()
    doc.id = kwargs.get("id", uuid4())
    doc.title = kwargs.get("title", "测试文档")
    doc.doc_type = kwargs.get("doc_type", "MISC")
    doc.file_name = kwargs.get("file_name", "test.pdf")
    doc.tags = kwargs.get("tags", [])
    doc.page_count = kwargs.get("page_count", 10)
    doc.confidence = kwargs.get("confidence", 0.0)
    doc.ingest_mode = kwargs.get("ingest_mode", "AUTO")
    doc.is_expired = kwargs.get("is_expired", False)
    doc.expire_date = kwargs.get("expire_date", None)
    doc.created_at = kwargs.get("created_at", datetime.now(UTC))
    return doc


@pytest.fixture
def mock_session() -> MagicMock:
    """Mock AsyncSession"""
    session = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def service(mock_session: MagicMock) -> KnowledgeService:
    svc = KnowledgeService(mock_session)
    svc.kb_repo = MagicMock()
    return svc


class TestGetStats:
    """KnowledgeService.get_stats 测试"""

    @pytest.mark.asyncio
    async def test_empty_knowledge_base(self, service: KnowledgeService) -> None:
        """空知识库统计：无过期文档，时效性得满分 30"""
        service.kb_repo.get_category_counts = AsyncMock(return_value={})
        service.kb_repo.get_expired_ratio = AsyncMock(return_value=0.0)
        service.kb_repo.get_recent_30d_count = AsyncMock(return_value=0)
        service.kb_repo.get_expiring_soon = AsyncMock(return_value=[])

        result = await service.get_stats()

        assert isinstance(result, KnowledgeStatsResponse)
        assert result.total_documents == 0
        # 空库：覆盖度 0 + 时效性 30(无过期) + 活跃度 0 = 30
        assert result.health_score == 30.0
        assert len(result.category_stats) == 5
        assert all(cs.count == 0 for cs in result.category_stats)
        assert result.expiring_soon == []

    @pytest.mark.asyncio
    async def test_health_score_calculation(self, service: KnowledgeService) -> None:
        """健康度评分计算验证"""
        # 构造分类统计
        category_counts = {
            "QUALIFICATION": {"total": 10, "expired": 2},
            "PERFORMANCE": {"total": 20, "expired": 0},
            "PERSONNEL": {"total": 5, "expired": 0},
            "SOLUTION": {"total": 8, "expired": 0},
            "MISC": {"total": 3, "expired": 0},
        }
        service.kb_repo.get_category_counts = AsyncMock(return_value=category_counts)
        # 过期率 10%（有 expire_date 的文档中 10% 过期）
        service.kb_repo.get_expired_ratio = AsyncMock(return_value=0.1)
        # 近30天新增 5 篇
        service.kb_repo.get_recent_30d_count = AsyncMock(return_value=5)
        service.kb_repo.get_expiring_soon = AsyncMock(return_value=[])

        result = await service.get_stats()

        # 手工验证算法
        # coverage = min(40, 20*0.5 + 10*0.3 + 5*0.1 + 8*0.5) = min(40, 10+3+0.5+4) = 17.5
        # timeliness = 30 * (1 - 0.1) = 27.0
        # activity = min(30, 5*3) = 15.0
        # health_score = 17.5 + 27.0 + 15.0 = 59.5
        assert result.total_documents == 46
        assert result.health_score == pytest.approx(59.5, rel=1e-2)

    @pytest.mark.asyncio
    async def test_health_score_max_100(self, service: KnowledgeService) -> None:
        """健康度评分上限 100"""
        category_counts = {
            "QUALIFICATION": {"total": 100, "expired": 0},
            "PERFORMANCE": {"total": 100, "expired": 0},
            "PERSONNEL": {"total": 100, "expired": 0},
            "SOLUTION": {"total": 100, "expired": 0},
        }
        service.kb_repo.get_category_counts = AsyncMock(return_value=category_counts)
        service.kb_repo.get_expired_ratio = AsyncMock(return_value=0.0)
        service.kb_repo.get_recent_30d_count = AsyncMock(return_value=100)
        service.kb_repo.get_expiring_soon = AsyncMock(return_value=[])

        result = await service.get_stats()

        # coverage = min(40, 100*0.5 + 100*0.3 + 100*0.1 + 100*0.5) = 40
        # timeliness = 30 * 1 = 30
        # activity = min(30, 100*3) = 30
        # total = 100
        assert result.health_score == 100.0

    @pytest.mark.asyncio
    async def test_category_stats_mapping(self, service: KnowledgeService) -> None:
        """分类统计映射验证（DB → API 分类）"""
        category_counts = {
            "QUALIFICATION": {"total": 5, "expired": 1},
            "PERFORMANCE": {"total": 10, "expired": 0},
            "PERSONNEL": {"total": 3, "expired": 0},
            "SOLUTION": {"total": 7, "expired": 2},
            "MISC": {"total": 2, "expired": 0},
        }
        service.kb_repo.get_category_counts = AsyncMock(return_value=category_counts)
        service.kb_repo.get_expired_ratio = AsyncMock(return_value=0.0)
        service.kb_repo.get_recent_30d_count = AsyncMock(return_value=0)
        service.kb_repo.get_expiring_soon = AsyncMock(return_value=[])

        result = await service.get_stats()

        mapping = {
            "QUALIFICATION": (5, 1),
            "PERFORMANCE": (10, 0),
            "PERSONNEL": (3, 0),
            "SOLUTION_TEMPLATE": (7, 2),
            "GENERAL": (2, 0),
        }
        for cs in result.category_stats:
            expected_count, expected_expired = mapping[cs.category]
            assert cs.count == expected_count
            assert cs.expired_count == expected_expired

    @pytest.mark.asyncio
    async def test_expiring_soon(self, service: KnowledgeService) -> None:
        """即将过期文档列表"""
        doc1 = _make_kb_document(
            title="证书A", doc_type="QUALIFICATION", expire_date=datetime.now(UTC).date() + timedelta(days=7)
        )
        doc2 = _make_kb_document(
            title="证书B", doc_type="QUALIFICATION", expire_date=datetime.now(UTC).date() + timedelta(days=15)
        )
        service.kb_repo.get_category_counts = AsyncMock(return_value={})
        service.kb_repo.get_expired_ratio = AsyncMock(return_value=0.0)
        service.kb_repo.get_recent_30d_count = AsyncMock(return_value=0)
        service.kb_repo.get_expiring_soon = AsyncMock(return_value=[doc1, doc2])

        result = await service.get_stats()

        assert len(result.expiring_soon) == 2
        assert result.expiring_soon[0].doc_id == str(doc1.id)
        assert result.expiring_soon[0].title == "证书A"
        assert result.expiring_soon[1].title == "证书B"

    @pytest.mark.asyncio
    async def test_no_expire_date_documents(self, service: KnowledgeService) -> None:
        """无 expire_date 文档时 expired_ratio 应为 0，时效性得满分 30"""
        service.kb_repo.get_category_counts = AsyncMock(return_value={})
        service.kb_repo.get_expired_ratio = AsyncMock(return_value=0.0)
        service.kb_repo.get_recent_30d_count = AsyncMock(return_value=0)
        service.kb_repo.get_expiring_soon = AsyncMock(return_value=[])

        result = await service.get_stats()

        # 无 expire_date 文档时，过期率为 0，时效性得满分 30
        # 覆盖度 0 + 时效性 30 + 活跃度 0 = 30
        assert result.health_score == 30.0
