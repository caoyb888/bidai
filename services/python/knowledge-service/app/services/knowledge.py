# ============================================================
# 知识库业务逻辑层 — Service
# ============================================================

from typing import BinaryIO, Literal, cast
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.es_client import ESClient
from app.ai.hybrid_retriever import HybridRetriever
from app.ai.milvus_client import MilvusClient
from app.ai.tasks import process_document_task
from app.core.config import settings
from app.core.exceptions import (
    FileTooLargeError,
    InvalidFileTypeError,
    NotFoundError,
    SearchServiceError,
    StorageError,
)
from app.core.logging import logger
from app.models.kb_document import KbDocument
from app.repositories.ai_task import AiTaskRepository
from app.repositories.kb_chunk import KbChunkRepository
from app.repositories.knowledge import KnowledgeRepository
from app.schemas.base import (
    CategoryStat,
    ExpiringSoonItem,
    KnowledgeDocument,
    KnowledgeDocumentListResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
    KnowledgeStatsResponse,
    KnowledgeUploadResponse,
)
from app.utils.minio_client import MinioClient, compute_sha256, get_file_extension


class KnowledgeService:
    """知识库业务服务"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.kb_repo = KnowledgeRepository(session)
        self.chunk_repo = KbChunkRepository(session)
        self.task_repo = AiTaskRepository(session)
        self.minio = MinioClient()
        self.retriever = HybridRetriever()

    @staticmethod
    def _map_doc_category(doc_category: str) -> str:
        """将 API 的 doc_category 映射到数据库 document_type 枚举值"""
        mapping = {
            "QUALIFICATION": "QUALIFICATION",
            "PERFORMANCE": "PERFORMANCE",
            "PERSONNEL": "PERSONNEL",
            "SOLUTION_TEMPLATE": "SOLUTION",
            "GENERAL": "MISC",
        }
        return mapping.get(doc_category, "MISC")

    @staticmethod
    def _map_doc_category_reverse(doc_type: str) -> str:
        """将数据库 document_type 枚举值映射到 API 的 doc_category"""
        mapping = {
            "QUALIFICATION": "QUALIFICATION",
            "PERFORMANCE": "PERFORMANCE",
            "PERSONNEL": "PERSONNEL",
            "SOLUTION": "SOLUTION_TEMPLATE",
            "MISC": "GENERAL",
        }
        return mapping.get(doc_type, "GENERAL")

    @classmethod
    def _to_knowledge_document(cls, doc: KbDocument) -> KnowledgeDocument:
        """将 ORM 模型转换为 API 响应模型"""
        doc_category = cls._map_doc_category_reverse(str(doc.doc_type))
        file_type = get_file_extension(str(doc.file_name)) if doc.file_name else ""
        created_at = (
            doc.created_at.isoformat()
            if doc.created_at is not None
            else ""
        )
        return KnowledgeDocument(
            id=str(doc.id),
            title=str(doc.title),
            doc_category=cast(
                "Literal['QUALIFICATION', 'PERFORMANCE', 'PERSONNEL', 'SOLUTION_TEMPLATE', 'GENERAL']",
                doc_category,
            ),
            tags=list(doc.tags) if doc.tags else [],
            file_type=file_type,
            page_count=int(doc.page_count) if doc.page_count is not None else None,
            confidence=float(doc.confidence) if doc.confidence is not None else 0.0,
            ingest_mode=cast(
                "Literal['AUTO', 'MANUAL_CONFIRM', 'MANUAL']",
                str(doc.ingest_mode) if doc.ingest_mode is not None else "AUTO",
            ),
            is_expired=bool(doc.is_expired) if doc.is_expired is not None else False,
            created_at=created_at,
        )

    async def upload_document(
        self,
        file_data: BinaryIO,
        file_name: str,
        mime_type: str,
        doc_category: str,
        title: str | None,
        tags: list[str],
        user_id: str,
    ) -> KnowledgeUploadResponse:
        """
        上传文档入库

        流程：类型校验 → 大小校验 → 计算 SHA-256 → 查重 → 存 MinIO → 写 DB → 发 Celery 任务
        """
        # 映射 doc_category 到数据库枚举值
        db_doc_type = self._map_doc_category(doc_category)
        # 1. 文件类型白名单校验
        ext = get_file_extension(file_name)
        if ext not in settings.upload_allowed_extensions:
            logger.warning(
                "Invalid file type uploaded",
                extra={"file_name": file_name, "extension": ext, "user_id": user_id},
            )
            raise InvalidFileTypeError(ext)

        # 2. 文件大小限制校验
        file_data.seek(0, 2)  # seek to end
        file_size = file_data.tell()
        file_data.seek(0)
        size_mb = file_size / (1024 * 1024)
        if size_mb > settings.upload_max_size_mb:
            logger.warning(
                "File too large",
                extra={
                    "file_name": file_name,
                    "size_mb": round(size_mb, 2),
                    "max_mb": settings.upload_max_size_mb,
                    "user_id": user_id,
                },
            )
            raise FileTooLargeError(size_mb, settings.upload_max_size_mb)

        # 3. 计算 SHA-256
        file_hash = compute_sha256(file_data)

        # 4. 哈希去重检查
        existing = await self.kb_repo.get_by_file_hash(file_hash)
        if existing is not None:
            logger.info(
                "Duplicate file detected",
                extra={
                    "file_hash": file_hash,
                    "existing_doc_id": str(existing.id),
                    "user_id": user_id,
                },
            )
            return KnowledgeUploadResponse(
                task_id="",
                status="SUCCESS",
                poll_url="",
                estimated_seconds=0,
                document_id=str(existing.id),
                is_duplicate=True,
            )

        # 5. 生成文档 ID 并上传 MinIO
        doc_id = uuid4()
        doc_title = title if title else file_name

        try:
            file_path = self.minio.upload_file(
                file_data=file_data,
                file_name=file_name,
                mime_type=mime_type,
                doc_id=str(doc_id),
            )
        except StorageError:
            raise
        except Exception as exc:
            logger.error(
                "MinIO upload failed",
                extra={"doc_id": str(doc_id), "file_name": file_name},
                exc_info=True,
            )
            raise StorageError("文件上传失败") from exc

        # 6. 写入 kb_documents 记录
        doc = KbDocument(
            id=doc_id,
            doc_type=db_doc_type,
            title=doc_title,
            file_path=file_path,
            file_name=file_name,
            file_size_bytes=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            parse_status="PENDING",
            tags=tags if tags else [],
            created_by=user_id,
            updated_by=user_id,
        )
        await self.kb_repo.create(doc)

        # 7. 提交 Celery 异步任务（占位）
        celery_task = process_document_task.delay(str(doc_id))

        # 8. 写入 ai_tasks 记录
        task = await self.task_repo.create(
            task_type="DOC_PARSE",
            ref_type="KB_DOCUMENT",
            ref_id=doc_id,
            celery_task_id=celery_task.id,
            input_payload={"doc_id": str(doc_id), "file_path": file_path},
            created_by=user_id,
        )

        await self.session.commit()

        logger.info(
            "Document uploaded successfully",
            extra={
                "doc_id": str(doc_id),
                "task_id": str(task.id),
                "celery_task_id": celery_task.id,
                "user_id": user_id,
                "file_size_bytes": file_size,
            },
        )

        return KnowledgeUploadResponse(
            task_id=str(task.id),
            status="PENDING",
            poll_url=f"/api/v1/tasks/{task.id}",
            estimated_seconds=30,
            document_id=str(doc_id),
            is_duplicate=False,
        )

    async def search_knowledge(
        self,
        request: KnowledgeSearchRequest,
    ) -> KnowledgeSearchResponse:
        """
        混合检索知识库

        流程：HybridRetriever（Milvus + ES + Rerank）→ 反查 PG 补充元数据 → 组装响应
        """
        try:
            results = await self.retriever.retrieve(
                query=request.query,
                top_k=request.top_k,
                doc_category=request.doc_category,
            )
        except Exception as exc:
            logger.error("Hybrid retrieval failed", extra={"query": request.query, "error": str(exc)})
            raise SearchServiceError("检索服务暂时不可用，请稍后重试") from exc

        if not results:
            return KnowledgeSearchResponse(results=[], total_found=0)

        # 反查 PG 补充 Milvus 结果缺失的 content 和 doc_title
        chunk_ids = [r.chunk_id for r in results]
        chunks = await self.chunk_repo.get_by_chunk_ids(chunk_ids)
        chunk_map = {str(c.id): c for c in chunks}

        # 同时查询文档标题（Milvus 结果可能缺少 doc_title）
        doc_ids = list({r.doc_id for r in results})
        doc_map: dict[str, str] = {}
        for doc_id in doc_ids:
            doc = await self.kb_repo.get_by_id(doc_id)
            if doc:
                doc_map[doc_id] = str(doc.title)

        search_results: list[KnowledgeSearchResult] = []
        for r in results:
            chunk = chunk_map.get(r.chunk_id)
            # 优先使用 PG 中的内容，fallback 到检索结果中的 content
            content: str = str(chunk.content) if chunk else (r.content or "")
            doc_title: str = doc_map.get(r.doc_id, r.doc_title or "")
            page_no: int | None = int(chunk.page_no) if chunk and chunk.page_no is not None else r.page_no

            search_results.append(
                KnowledgeSearchResult(
                    chunk_id=r.chunk_id,
                    doc_id=r.doc_id,
                    doc_title=doc_title,
                    content=content,
                    page_no=page_no,
                    score=round(r.score, 4),
                    highlight=r.highlight,
                )
            )

        return KnowledgeSearchResponse(
            results=search_results,
            total_found=len(search_results),
        )

    async def list_documents(
        self,
        page: int,
        page_size: int,
        doc_category: str | None,
        tags: list[str] | None,
        is_expired: bool | None,
        keyword: str | None,
    ) -> KnowledgeDocumentListResponse:
        """获取知识库文档列表（支持分页和筛选）"""
        doc_type = self._map_doc_category(doc_category) if doc_category else None

        total = await self.kb_repo.count_documents(
            doc_type=doc_type,
            tags=tags,
            is_expired=is_expired,
            keyword=keyword,
        )
        docs = await self.kb_repo.list_documents(
            doc_type=doc_type,
            tags=tags,
            is_expired=is_expired,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )

        items = [self._to_knowledge_document(d) for d in docs]
        total_pages = (total + page_size - 1) // page_size

        return KnowledgeDocumentListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_document(self, doc_id: str) -> KnowledgeDocument:
        """获取知识库文档详情"""
        doc = await self.kb_repo.get_by_id(doc_id)
        if doc is None:
            raise NotFoundError("知识库文档")
        return self._to_knowledge_document(doc)

    async def delete_document(self, doc_id: str, user_id: str) -> None:
        """删除知识库文档（软删除 + 同步清理向量/索引）"""
        # 1. 确认文档存在
        doc = await self.kb_repo.get_by_id(doc_id)
        if doc is None:
            raise NotFoundError("知识库文档")

        # 2. DB 层软删除 + 物理删除 chunks（同一事务）
        await self.kb_repo.soft_delete(doc_id, user_id)
        deleted_chunks = await self.chunk_repo.delete_by_doc_id(doc_id)
        await self.session.commit()

        logger.info(
            "Document soft deleted from DB",
            extra={"doc_id": doc_id, "user_id": user_id, "deleted_chunks": deleted_chunks},
        )

        # 3. 同步清理 Milvus 向量
        try:
            MilvusClient().delete_by_doc_id(doc_id)
        except Exception as exc:
            logger.error(
                "Milvus vector cleanup failed during document deletion",
                extra={"doc_id": doc_id, "error": str(exc)},
            )

        # 4. 同步清理 ES 索引
        try:
            await ESClient().delete_by_doc_id(doc_id)
        except Exception as exc:
            logger.error(
                "ES index cleanup failed during document deletion",
                extra={"doc_id": doc_id, "error": str(exc)},
            )

        logger.info(
            "Document deletion completed",
            extra={"doc_id": doc_id, "user_id": user_id},
        )

    async def get_stats(self) -> KnowledgeStatsResponse:
        """获取知识库统计信息（含健康度评分、各分类文档数、过期预警）

        健康度评分算法（与数据库设计文档 mv_kb_health_score 保持一致）：
        - 覆盖度得分（40分）：performance×0.5 + qualification×0.3 + personnel×0.1 + solution×0.5，上限40
        - 时效性得分（30分）：30 × (1 − 过期率)
        - 活跃度得分（30分）：近30天新增数 × 3，上限30
        - 总分 = max(0, min(100, 覆盖度 + 时效性 + 活跃度))
        """
        # 1. 各分类文档统计
        category_counts = await self.kb_repo.get_category_counts()

        # 2. 过期率 & 活跃度
        expired_ratio = await self.kb_repo.get_expired_ratio()
        recent_30d_count = await self.kb_repo.get_recent_30d_count()

        # 3. 即将过期文档（30天内）
        expiring_docs = await self.kb_repo.get_expiring_soon(days=30)

        # 4. 组装 category_stats（按 API 层分类维度）
        api_categories = [
            "QUALIFICATION",
            "PERFORMANCE",
            "PERSONNEL",
            "SOLUTION_TEMPLATE",
            "GENERAL",
        ]
        db_keys = ["QUALIFICATION", "PERFORMANCE", "PERSONNEL", "SOLUTION", "MISC"]
        category_stats: list[CategoryStat] = []
        total_documents = 0

        for api_cat, db_key in zip(api_categories, db_keys):
            stats = category_counts.get(db_key, {"total": 0, "expired": 0})
            total_documents += stats["total"]
            category_stats.append(
                CategoryStat(
                    category=api_cat,  # type: ignore[arg-type]
                    count=stats["total"],
                    expired_count=stats["expired"],
                )
            )

        # 5. 计算健康度评分
        qualification_count = category_counts.get("QUALIFICATION", {}).get("total", 0)
        performance_count = category_counts.get("PERFORMANCE", {}).get("total", 0)
        personnel_count = category_counts.get("PERSONNEL", {}).get("total", 0)
        solution_count = category_counts.get("SOLUTION", {}).get("total", 0)

        coverage_score = min(
            40.0,
            performance_count * 0.5
            + qualification_count * 0.3
            + personnel_count * 0.1
            + solution_count * 0.5,
        )
        timeliness_score = 30.0 * (1.0 - expired_ratio)
        activity_score = min(30.0, recent_30d_count * 3.0)
        health_score = max(0.0, min(100.0, coverage_score + timeliness_score + activity_score))

        # 6. 组装 expiring_soon
        expiring_soon = [
            ExpiringSoonItem(
                doc_id=str(doc.id),
                title=str(doc.title),
                expire_date=str(doc.expire_date) if doc.expire_date else "",
            )
            for doc in expiring_docs
        ]

        logger.info(
            "Knowledge stats calculated",
            extra={
                "total_documents": total_documents,
                "health_score": round(health_score, 2),
                "expired_ratio": round(expired_ratio, 4),
                "recent_30d_count": recent_30d_count,
                "expiring_soon_count": len(expiring_soon),
            },
        )

        return KnowledgeStatsResponse(
            total_documents=total_documents,
            health_score=round(health_score, 2),
            category_stats=category_stats,
            expiring_soon=expiring_soon,
        )
