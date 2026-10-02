import "server-only";
import { DeleteObjectCommand, PutObjectCommand, S3Client } from "@aws-sdk/client-s3";

// Any S3-compatible store (Supabase Storage, Cloudflare R2, Backblaze B2...).
function getStorageClient() {
  return new S3Client({
    region: process.env.STORAGE_REGION || "us-east-1",
    endpoint: process.env.STORAGE_ENDPOINT_URL,
    forcePathStyle: true,
    credentials: {
      accessKeyId: process.env.STORAGE_ACCESS_KEY_ID!,
      secretAccessKey: process.env.STORAGE_SECRET_ACCESS_KEY!,
    },
  });
}

/**
 * Uploads a file's bytes under `key`. Returns the object key, which is what
 * gets stored in the DB (resumes.file_key) -- the bucket is private, so
 * there's no public URL to return, and FastAPI reads the file back by this
 * same key when it needs to parse it (see core/storage.py).
 */
export async function uploadToStorage(
  key: string,
  body: Buffer,
  contentType: string
): Promise<string> {
  const client = getStorageClient();
  await client.send(
    new PutObjectCommand({
      Bucket: process.env.STORAGE_BUCKET_NAME!,
      Key: key,
      Body: body,
      ContentType: contentType,
    })
  );
  return key;
}

export async function deleteFromStorage(key: string): Promise<void> {
  const client = getStorageClient();
  await client.send(
    new DeleteObjectCommand({ Bucket: process.env.STORAGE_BUCKET_NAME!, Key: key })
  );
}
