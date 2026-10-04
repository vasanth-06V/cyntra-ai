from functools import lru_cache

import boto3
from botocore.config import Config

from app.core.config import settings


@lru_cache
def get_storage_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint_url,
        region_name=settings.storage_region or "us-east-1",
        aws_access_key_id=settings.storage_access_key_id,
        aws_secret_access_key=settings.storage_secret_access_key,
        config=Config(s3={"addressing_style": "path"}),
    )


# Resumes are limited to 500 KB at upload; never pull more than that (plus one
# byte, so an oversized object is still noticed) into memory.
MAX_DOWNLOAD_BYTES = 500 * 1024


def download_bytes(object_key: str) -> bytes:
    """Fetches a previously-uploaded file's raw bytes from object storage.
    Uploads happen from Next.js (Section 3: simple storage CRUD belongs
    there); FastAPI only reads a file back when it needs to parse it for RAG."""
    client = get_storage_client()
    response = client.get_object(Bucket=settings.storage_bucket_name, Key=object_key)
    return response["Body"].read(MAX_DOWNLOAD_BYTES + 1)
