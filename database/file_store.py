"""File storage adapter: local directory (dev) or S3-compatible (prod).

The database stores only metadata (files table); bytes live here. The local
adapter keeps development dependency-free; the S3 adapter is used when
STORAGE_URL/STORAGE_BUCKET are configured and boto3 is installed.
"""
from __future__ import annotations

import hashlib
import os
from typing import Optional, Tuple


class FileStore:
    """put/get/delete of binary blobs. Keys are relative storage keys like
    ``datasets/<project>/train.csv`` — never absolute paths."""

    def __init__(self, config: Optional[dict] = None):
        config = config or {}
        self.backend_kind = "local"
        self._s3 = None
        storage_url = (config.get("storage_url")
                       or os.environ.get("STORAGE_URL") or "").strip()
        bucket = (config.get("storage_bucket")
                  or os.environ.get("STORAGE_BUCKET") or "").strip()
        if storage_url and bucket:
            try:
                import boto3  # optional dependency
                self._s3 = boto3.client(
                    "s3",
                    endpoint_url=storage_url,
                    aws_access_key_id=os.environ.get("STORAGE_ACCESS_KEY_ID"),
                    aws_secret_access_key=os.environ.get("STORAGE_SECRET_ACCESS_KEY"),
                )
                self._bucket = bucket
                self.backend_kind = "s3"
            except Exception as e:
                print(f"[FILESTORE S3 WARNING]: {e} — falling back to local dir")
        if self._s3 is None:
            root = (config.get("root")
                    or os.environ.get("STORAGE_LOCAL_ROOT")
                    or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "object_store"))
            self._root = root
            os.makedirs(self._root, exist_ok=True)

    # ------------------------------------------------------------------ paths
    def _safe_key(self, key: str) -> str:
        key = key.replace("\\", "/").lstrip("/")
        if ".." in key.split("/"):
            raise ValueError(f"Invalid storage key: {key!r}")
        return key

    # ------------------------------------------------------------------- ops
    def put(self, key: str, data: bytes,
            content_type: Optional[str] = None) -> Tuple[str, int, str]:
        """Store bytes; returns (storage_key, size_bytes, sha256)."""
        key = self._safe_key(key)
        digest = hashlib.sha256(data).hexdigest()
        if self._s3 is not None:
            extra = {"ContentType": content_type} if content_type else None
            self._s3.put_object(Bucket=self._bucket, Key=key, Body=data,
                                **(extra or {}))
        else:
            path = os.path.join(self._root, key.replace("/", os.sep))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
        return key, len(data), digest

    def get(self, key: str) -> Optional[bytes]:
        key = self._safe_key(key)
        if self._s3 is not None:
            try:
                response = self._s3.get_object(Bucket=self._bucket, Key=key)
                return response["Body"].read()
            except Exception:
                return None
        path = os.path.join(self._root, key.replace("/", os.sep))
        if not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            return f.read()

    def delete(self, key: str) -> bool:
        key = self._safe_key(key)
        if self._s3 is not None:
            try:
                self._s3.delete_object(Bucket=self._bucket, Key=key)
                return True
            except Exception:
                return False
        path = os.path.join(self._root, key.replace("/", os.sep))
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def local_path(self, key: str) -> Optional[str]:
        """Local adapter only: absolute path of the stored object."""
        if self._s3 is not None:
            return None
        key = self._safe_key(key)
        path = os.path.join(self._root, key.replace("/", os.sep))
        return path if os.path.exists(path) else None


_default_file_store: Optional[FileStore] = None


def get_file_store() -> FileStore:
    global _default_file_store
    if _default_file_store is None:
        _default_file_store = FileStore()
    return _default_file_store


def record_file(repo, file_store: FileStore, key: str, data: bytes,
                file_type: Optional[str] = None,
                owner_user_id: Optional[str] = None) -> dict:
    """Store bytes and insert the files-table metadata row. Returns metadata."""
    import uuid
    storage_key, size, digest = file_store.put(key, data, content_type=file_type)
    file_id = str(uuid.uuid4())
    repo._execute(
        """INSERT INTO files (id, storage_key, storage_backend, file_type, size_bytes, hash_sha256, owner_user_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (file_id, storage_key, file_store.backend_kind, file_type, size, digest,
         owner_user_id))
    return {"id": file_id, "storageKey": storage_key, "sizeBytes": size,
            "sha256": digest, "backend": file_store.backend_kind}
