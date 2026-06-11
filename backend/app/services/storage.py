"""
对象存储服务 - MinIO 封装

特点：
- 懒加载：首次调用才连接，启动期 MinIO 不可达不会直接拒启
- 私有 bucket 策略：强制 Deny 匿名 GetObject / ListBucket
"""
from __future__ import annotations

import io
import json
import logging
import threading
from datetime import timedelta
from typing import Optional

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.exceptions import AppException, BadRequestError

logger = logging.getLogger(__name__)


_PRIVATE_BUCKET_POLICY = json.dumps(
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Deny",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject", "s3:ListBucket"],
                "Resource": [
                    f"arn:aws:s3:::{settings.MINIO_BUCKET}",
                    f"arn:aws:s3:::{settings.MINIO_BUCKET}/*",
                ],
            }
        ],
    }
)


class StorageUnavailable(AppException):
    def __init__(self, detail: str = "对象存储不可用"):
        super().__init__(detail, 503, "storage_unavailable")


class Storage:
    def __init__(self) -> None:
        self._client: Optional[Minio] = None
        self._lock = threading.Lock()

    def _get_client(self) -> Minio:
        if self._client is not None:
            return self._client
        with self._lock:
            if self._client is not None:
                return self._client
            try:
                client = Minio(
                    settings.MINIO_ENDPOINT,
                    access_key=settings.MINIO_ACCESS_KEY,
                    secret_key=settings.MINIO_SECRET_KEY,
                    secure=settings.MINIO_SECURE,
                )
                if not client.bucket_exists(settings.MINIO_BUCKET):
                    client.make_bucket(settings.MINIO_BUCKET)
                    logger.info("MinIO bucket 已创建: %s", settings.MINIO_BUCKET)
                # 不管刚建的还是已有的，都强制设一次私有策略
                client.set_bucket_policy(settings.MINIO_BUCKET, _PRIVATE_BUCKET_POLICY)
                logger.info("MinIO bucket 策略已设为私有: %s", settings.MINIO_BUCKET)
                self._client = client
            except S3Error as e:
                raise StorageUnavailable(f"MinIO 连接失败: {e}")
        return self._client

    def upload_data(
        self, object_name: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        client = self._get_client()
        client.put_object(
            settings.MINIO_BUCKET,
            object_name,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    def upload_file(
        self, object_name: str, file_path: str, content_type: str = "application/octet-stream"
    ) -> None:
        client = self._get_client()
        client.fput_object(
            settings.MINIO_BUCKET, object_name, file_path, content_type=content_type
        )

    def get_presigned_url(self, object_name: str, expires_seconds: int = 86400 * 7) -> str:
        client = self._get_client()
        return client.presigned_get_object(
            settings.MINIO_BUCKET,
            object_name,
            expires=timedelta(seconds=expires_seconds),
        )

    def get_data(self, object_name: str) -> bytes:
        client = self._get_client()
        response = client.get_object(settings.MINIO_BUCKET, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete_object(self, object_name: str) -> None:
        client = self._get_client()
        client.remove_object(settings.MINIO_BUCKET, object_name)

    def object_exists(self, object_name: str) -> bool:
        try:
            client = self._get_client()
            client.stat_object(settings.MINIO_BUCKET, object_name)
            return True
        except S3Error:
            return False
        except StorageUnavailable:
            return False


# 全局单例（懒加载）
storage = Storage()
