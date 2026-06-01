#!/usr/bin/env python3
# ============================================================
# 批量历史数据导入工具（CLI 脚本）
# Sprint: S1-2-009
#
# 用法示例:
#   python -m app.cli.batch_import --source-dir /data/historical_docs --concurrency 5
#
# 目录结构约定:
#   /data/historical_docs/
#     ├── qualification/   → QUALIFICATION
#     ├── performance/     → PERFORMANCE
#     ├── personnel/       → PERSONNEL
#     ├── solution/        → SOLUTION_TEMPLATE
#     └── general/         → GENERAL
# ============================================================

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings
from app.core.exceptions import (
    FileTooLargeError,
    InvalidFileTypeError,
    StorageError,
)
from app.core.logging import logger
from app.db import AsyncSessionLocal
from app.services.knowledge import KnowledgeService
from app.utils.minio_client import get_file_extension

# ---------------------------------------------------------------
# 扩展名 → MIME 类型映射（用于 MinIO Content-Type）
# ---------------------------------------------------------------
_EXT_TO_MIME: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
}

# ---------------------------------------------------------------
# 目录名 → 文档分类映射（不区分大小写）
# ---------------------------------------------------------------
_DIR_TO_CATEGORY: dict[str, str] = {
    "qualification": "QUALIFICATION",
    "qualifications": "QUALIFICATION",
    "performance": "PERFORMANCE",
    "performances": "PERFORMANCE",
    "case": "PERFORMANCE",
    "cases": "PERFORMANCE",
    "personnel": "PERSONNEL",
    "people": "PERSONNEL",
    "staff": "PERSONNEL",
    "human": "PERSONNEL",
    "solution": "SOLUTION_TEMPLATE",
    "solutions": "SOLUTION_TEMPLATE",
    "template": "SOLUTION_TEMPLATE",
    "templates": "SOLUTION_TEMPLATE",
    "general": "GENERAL",
    "misc": "GENERAL",
    "others": "GENERAL",
    "other": "GENERAL",
}

# 支持扩展名（与 settings 保持一致）
_ALLOWED_EXTENSIONS: set[str] = settings.upload_allowed_extensions


# ---------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------
@dataclass
class ImportFileItem:
    """单个待导入文件信息"""

    file_path: Path
    doc_category: str
    relative_path: str
    status: str = "PENDING"
    error_message: str | None = None
    document_id: str | None = None
    is_duplicate: bool = False
    duration_ms: float = 0.0


@dataclass
class ImportReport:
    """导入汇总报告"""

    started_at: str
    finished_at: str = ""
    source_dir: str = ""
    total_files: int = 0
    success_count: int = 0
    duplicate_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    total_duration_ms: float = 0.0
    files: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ---------------------------------------------------------------
# 分类推断
# ---------------------------------------------------------------
def infer_category(dir_name: str) -> str:
    """根据目录名推断文档分类"""
    key = dir_name.lower().strip()
    return _DIR_TO_CATEGORY.get(key, "GENERAL")


def scan_source_dir(source_dir: Path) -> list[ImportFileItem]:
    """
    扫描源目录，收集所有待导入文件

    规则:
    - 仅扫描 source_dir 下的一级子目录
    - 子目录名映射到 doc_category（无法识别则归为 GENERAL）
    - 跳过隐藏文件、非白名单扩展名的文件
    - 不递归扫描子目录的子目录
    """
    items: list[ImportFileItem] = []

    if not source_dir.exists():
        logger.error("Source directory does not exist", extra={"path": str(source_dir)})
        return items

    if not source_dir.is_dir():
        logger.error("Source path is not a directory", extra={"path": str(source_dir)})
        return items

    for subdir in sorted(source_dir.iterdir()):
        if not subdir.is_dir():
            continue
        if subdir.name.startswith("."):
            continue

        category = infer_category(subdir.name)
        if category == "GENERAL" and subdir.name.lower() not in _DIR_TO_CATEGORY:
            logger.warning(
                "Unrecognized subdirectory, defaulting to GENERAL",
                extra={"subdir": subdir.name, "path": str(subdir)},
            )

        for file_path in sorted(subdir.iterdir()):
            if not file_path.is_file():
                continue
            if file_path.name.startswith("."):
                continue

            ext = get_file_extension(file_path.name)
            if ext not in _ALLOWED_EXTENSIONS:
                logger.warning(
                    "Skipping unsupported file type",
                    extra={"file": file_path.name, "extension": ext},
                )
                continue

            relative = str(file_path.relative_to(source_dir))
            items.append(
                ImportFileItem(
                    file_path=file_path,
                    doc_category=category,
                    relative_path=relative,
                )
            )

    logger.info(
        "Source directory scan completed",
        extra={
            "source_dir": str(source_dir),
            "total_files": len(items),
            "categories": list({item.doc_category for item in items}),
        },
    )
    return items


# ---------------------------------------------------------------
# 单文件上传
# ---------------------------------------------------------------
async def upload_single(
    item: ImportFileItem,
    user_id: str,
) -> None:
    """上传单个文件"""
    start_time = time.perf_counter()
    item.status = "UPLOADING"

    async with AsyncSessionLocal() as session:
        service = KnowledgeService(session)
        file_data: BinaryIO | None = None
        try:
            file_data = open(item.file_path, "rb")
            ext = get_file_extension(item.file_path.name)
            mime_type = _EXT_TO_MIME.get(ext, "application/octet-stream")
            result = await service.upload_document(
                file_data=file_data,
                file_name=item.file_path.name,
                mime_type=mime_type,
                doc_category=item.doc_category,
                title=item.file_path.stem,
                tags=[],
                user_id=user_id,
            )
            item.duration_ms = (time.perf_counter() - start_time) * 1000
            item.document_id = result.document_id
            item.is_duplicate = result.is_duplicate
            item.status = "SUCCESS" if not result.is_duplicate else "DUPLICATE"
        except InvalidFileTypeError as exc:
            item.status = "FAILED"
            item.error_message = f"不支持的文件类型: {exc}"
        except FileTooLargeError as exc:
            item.status = "FAILED"
            item.error_message = f"文件过大: {exc}"
        except StorageError as exc:
            item.status = "FAILED"
            item.error_message = f"存储失败: {exc}"
        except Exception as exc:
            item.status = "FAILED"
            item.error_message = f"上传异常: {type(exc).__name__}: {exc}"
        finally:
            if file_data is not None:
                file_data.close()


# ---------------------------------------------------------------
# 并发控制 + 进度打印
# ---------------------------------------------------------------
async def run_import(
    items: list[ImportFileItem],
    concurrency: int,
    user_id: str,
) -> None:
    """并发导入所有文件，带进度报告"""
    semaphore = asyncio.Semaphore(concurrency)
    total = len(items)
    completed = 0

    async def _worker(item: ImportFileItem) -> None:
        nonlocal completed
        async with semaphore:
            await upload_single(item, user_id)
            completed += 1
            # 实时进度输出
            _print_progress(completed, total, item)

    tasks = [asyncio.create_task(_worker(item)) for item in items]
    await asyncio.gather(*tasks, return_exceptions=True)


def _print_progress(completed: int, total: int, item: ImportFileItem) -> None:
    """控制台实时进度输出"""
    pct = completed / total * 100 if total > 0 else 100
    status_icon = {
        "SUCCESS": "✓",
        "DUPLICATE": "↻",
        "FAILED": "✗",
    }.get(item.status, "?")
    print(
        f"[{completed:>3}/{total}] ({pct:5.1f}%) {status_icon} {item.relative_path:<50} "
        f"→ {item.doc_category:<18} "
        f"({item.duration_ms:>6.1f}ms)"
        f"{f' [ERR: {item.error_message}]' if item.error_message else ''}",
        flush=True,
    )


# ---------------------------------------------------------------
# 汇总报告
# ---------------------------------------------------------------
def generate_report(
    items: list[ImportFileItem],
    started_at: str,
    source_dir: Path,
    total_duration_ms: float,
) -> ImportReport:
    """生成导入汇总报告"""
    report = ImportReport(
        started_at=started_at,
        finished_at=datetime.now().isoformat(),
        source_dir=str(source_dir),
        total_files=len(items),
        total_duration_ms=round(total_duration_ms, 2),
    )

    for item in items:
        report.files.append(
            {
                "relative_path": item.relative_path,
                "doc_category": item.doc_category,
                "status": item.status,
                "document_id": item.document_id,
                "is_duplicate": item.is_duplicate,
                "duration_ms": round(item.duration_ms, 2),
                "error_message": item.error_message,
            }
        )
        if item.status == "SUCCESS":
            report.success_count += 1
        elif item.status == "DUPLICATE":
            report.duplicate_count += 1
        elif item.status == "FAILED":
            report.failed_count += 1
        else:
            report.skipped_count += 1

    return report


def print_summary(report: ImportReport) -> None:
    """控制台输出汇总"""
    print("\n" + "=" * 70)
    print("批量导入完成")
    print("=" * 70)
    print(f"  源目录:      {report.source_dir}")
    print(f"  总文件数:    {report.total_files}")
    print(f"  成功:        {report.success_count}")
    print(f"  重复跳过:    {report.duplicate_count}")
    print(f"  失败:        {report.failed_count}")
    print(f"  未处理:      {report.skipped_count}")
    print(f"  总耗时:      {report.total_duration_ms / 1000:.2f}s")
    print(f"  开始时间:    {report.started_at}")
    print(f"  结束时间:    {report.finished_at}")

    if report.failed_count > 0:
        print("\n  失败明细:")
        for f in report.files:
            if f["status"] == "FAILED":
                print(f"    - {f['relative_path']}: {f['error_message']}")
    print("=" * 70)


# ---------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="batch_import",
        description="批量历史数据导入工具 — 按目录结构自动推断文档分类并上传入库",
    )
    parser.add_argument(
        "--source-dir", "-s",
        required=True,
        type=Path,
        help="源目录路径，包含按分类命名的子目录",
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=5,
        help="并发上传路数（默认 5）",
    )
    parser.add_argument(
        "--user-id", "-u",
        type=str,
        default="system/batch-import",
        help="执行导入的系统用户 ID（默认 system/batch-import）",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="导入报告输出路径（JSON 格式）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅扫描文件并输出分类映射，不实际上传",
    )
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started_at = datetime.now().isoformat()

    # 扫描文件
    print(f"扫描源目录: {args.source_dir.resolve()}")
    items = scan_source_dir(args.source_dir)

    if not items:
        print("未找到可导入的文件，请检查目录结构。")
        return 1

    print(f"共发现 {len(items)} 个待导入文件")
    print("-" * 70)

    if args.dry_run:
        for item in items:
            print(f"  [DRY-RUN] {item.relative_path} → {item.doc_category}")
        return 0

    # 执行导入
    total_start = time.perf_counter()
    await run_import(items, args.concurrency, args.user_id)
    total_duration_ms = (time.perf_counter() - total_start) * 1000

    # 生成报告
    report = generate_report(items, started_at, args.source_dir, total_duration_ms)
    print_summary(report)

    # 写入报告文件
    if args.output:
        args.output.write_text(report.to_json(), encoding="utf-8")
        print(f"\n报告已保存: {args.output.resolve()}")

    return 0 if report.failed_count == 0 else 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
