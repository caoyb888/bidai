# ============================================================
# MinIO 客户端封装 — 文件上传/下载/删除
# ============================================================

import hashlib
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.exceptions import StorageError


class MinioClient:
    """MinIO 客户端封装"""

    def __init__(self) -> None:
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_kb_bucket

    def ensure_bucket(self) -> None:
        """确保 Bucket 存在"""
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def upload_file(
        self,
        file_data: BinaryIO,
        file_name: str,
        mime_type: str,
        doc_id: str,
    ) -> str:
        """
        上传文件到 MinIO

        返回: MinIO 对象路径（不含 bucket）
        """
        self.ensure_bucket()

        ext = Path(file_name).suffix.lstrip(".").lower()
        now = datetime.utcnow()
        object_path = f"{now.year}/{now.month:02d}/{doc_id}/{doc_id}.{ext}"

        file_data.seek(0)
        file_size = len(file_data.read())
        file_data.seek(0)

        try:
            self.client.put_object(
                self.bucket,
                object_path,
                file_data,
                file_size,
                content_type=mime_type,
            )
        except S3Error as exc:
            raise StorageError(f"MinIO 上传失败: {exc}") from exc

        return object_path

    def delete_file(self, object_path: str) -> None:
        """删除 MinIO 对象"""
        try:
            self.client.remove_object(self.bucket, object_path)
        except S3Error as exc:
            raise StorageError(f"MinIO 删除失败: {exc}") from exc

    def download_file(self, object_path: str, local_path: str) -> None:
        """下载 MinIO 对象到本地路径"""
        try:
            self.client.fget_object(self.bucket, object_path, local_path)
        except S3Error as exc:
            raise StorageError(f"MinIO 下载失败: {exc}") from exc

    def upload_text(self, content: str, object_path: str) -> str:
        """
        上传文本内容到 MinIO

        返回: MinIO 对象路径（不含 bucket）
        """
        from io import BytesIO

        self.ensure_bucket()
        data = content.encode("utf-8")
        stream = BytesIO(data)
        try:
            self.client.put_object(
                self.bucket,
                object_path,
                stream,
                len(data),
                content_type="text/plain; charset=utf-8",
            )
        except S3Error as exc:
            raise StorageError(f"MinIO 文本上传失败: {exc}") from exc
        return object_path


def compute_sha256(file_data: BinaryIO) -> str:
    """计算文件 SHA-256 哈希（流式）"""
    sha256 = hashlib.sha256()
    file_data.seek(0)
    for chunk in iter(lambda: file_data.read(8192), b""):
        sha256.update(chunk)
    file_data.seek(0)
    return sha256.hexdigest()


def get_file_extension(file_name: str) -> str:
    """获取文件小写后缀（不含点）"""
    return Path(file_name).suffix.lstrip(".").lower()
