"""Thin wrapper around boto3 S3 for knowledge document storage."""

from __future__ import annotations

import uuid
from pathlib import Path

import boto3
from botocore.config import Config


class S3Client:
    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        access_key_id: str = "",
        secret_access_key: str = "",
        endpoint_url: str = "",
    ):
        self._bucket = bucket
        kwargs: dict = {"region_name": region, "config": Config(signature_version="s3v4")}
        if access_key_id:
            kwargs["aws_access_key_id"] = access_key_id
            kwargs["aws_secret_access_key"] = secret_access_key
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        self._s3 = boto3.client("s3", **kwargs)

    def _build_key(self, filename: str, category: str = "geral") -> str:
        ext = Path(filename).suffix
        unique = uuid.uuid4().hex[:8]
        safe_name = Path(filename).stem[:50]
        return f"knowledge/{category}/{safe_name}-{unique}{ext}"

    def upload(
        self, file_bytes: bytes, filename: str, content_type: str, category: str = "geral",
    ) -> str:
        key = self._build_key(filename, category)
        self._s3.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return key

    def download(self, key: str) -> bytes:
        response = self._s3.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    def delete(self, key: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=key)

    def presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )
