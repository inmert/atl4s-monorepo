"""Lazy, process-wide GCS client."""

from typing import Optional

from google.cloud import storage

from app.config import GCS_BUCKET

_client: Optional[storage.Client] = None


def bucket() -> storage.Bucket:
    global _client
    if _client is None:
        _client = storage.Client()
    return _client.bucket(GCS_BUCKET)
