"""MinIO bronze storage: hash-addressed, write-once objects."""
from __future__ import annotations

import io

from minio.error import S3Error

_MISSING = ("NoSuchKey", "NoSuchObject", "NoSuchBucket")


def object_key(cik: int, source: str, content_hash: str, suffix: str) -> str:
    """Object key under the bronze bucket, keyed by company/source/content hash."""
    return f"{cik}/{source}/{content_hash}{suffix}"


class BronzeStore:
    def __init__(self, client, bucket: str):
        self.client = client
        self.bucket = bucket

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put_if_absent(self, key: str, data: bytes, content_type: str) -> bool:
        """Write bytes only when the object does not exist. Never overwrite.

        Returns True when a new object was written, False when it already existed.
        """
        try:
            self.client.stat_object(self.bucket, key)
            return False
        except S3Error as error:
            if error.code not in _MISSING:
                raise
        self.client.put_object(
            self.bucket, key, io.BytesIO(data), length=len(data), content_type=content_type
        )
        return True
