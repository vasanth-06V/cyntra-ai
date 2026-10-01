from functools import lru_cache

import boto3

from app.core.config import settings


@lru_cache
def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
    )


def download_bytes(object_key: str) -> bytes:
    """Fetches a previously-uploaded file's raw bytes from R2. Uploads
    happen from Next.js (Section 3: simple storage CRUD belongs there);
    FastAPI only reads a file back when it needs to parse it for RAG."""
    client = get_r2_client()
    response = client.get_object(Bucket=settings.r2_bucket_name, Key=object_key)
    return response["Body"].read()
