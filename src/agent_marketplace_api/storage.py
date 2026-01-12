"""Storage service for S3/MinIO file operations."""

import asyncio
from dataclasses import dataclass
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError

from agent_marketplace_api.config import get_settings

settings = get_settings()


class StorageError(Exception):
    """Base exception for storage operations."""

    pass


class FileNotFoundError(StorageError):
    """Raised when a file is not found in storage."""

    pass


class UploadError(StorageError):
    """Raised when file upload fails."""

    pass


@dataclass
class UploadResult:
    """Result of a file upload operation."""

    key: str
    bucket: str
    size_bytes: int
    etag: str


class StorageService:
    """Service for S3/MinIO file storage operations."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        region: str | None = None,
    ) -> None:
        """Initialize storage service with S3 configuration."""
        self.endpoint_url = endpoint_url or settings.s3_endpoint
        self.access_key = access_key or settings.s3_access_key
        self.secret_key = secret_key or settings.s3_secret_key
        self.bucket = bucket or settings.s3_bucket
        self.region = region or settings.s3_region

        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
        )

    async def upload_file(
        self,
        key: str,
        file_data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> UploadResult:
        """Upload a file to S3/MinIO.

        Args:
            key: The S3 object key (path)
            file_data: File contents as bytes or file-like object
            content_type: MIME type of the file

        Returns:
            UploadResult with upload details

        Raises:
            UploadError: If upload fails
        """

        def _upload() -> UploadResult:
            try:
                # If bytes, we need to track size before upload
                if isinstance(file_data, bytes):
                    size = len(file_data)
                    response = self._client.put_object(
                        Bucket=self.bucket,
                        Key=key,
                        Body=file_data,
                        ContentType=content_type,
                    )
                else:
                    # For file-like objects, get size from seek
                    file_data.seek(0, 2)  # Seek to end
                    size = file_data.tell()
                    file_data.seek(0)  # Reset to beginning
                    response = self._client.put_object(
                        Bucket=self.bucket,
                        Key=key,
                        Body=file_data,
                        ContentType=content_type,
                    )

                etag = response.get("ETag", "").strip('"')
                return UploadResult(
                    key=key,
                    bucket=self.bucket,
                    size_bytes=size,
                    etag=etag,
                )
            except ClientError as e:
                raise UploadError(f"Failed to upload file: {e}") from e

        return await asyncio.to_thread(_upload)

    async def download_file(self, key: str) -> bytes:
        """Download a file from S3/MinIO.

        Args:
            key: The S3 object key (path)

        Returns:
            File contents as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
            StorageError: If download fails
        """

        def _download() -> bytes:
            try:
                response = self._client.get_object(Bucket=self.bucket, Key=key)
                data: bytes = response["Body"].read()
                return data
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code in ("404", "NoSuchKey"):
                    raise FileNotFoundError(f"File not found: {key}") from e
                raise StorageError(f"Failed to download file: {e}") from e

        return await asyncio.to_thread(_download)

    async def delete_file(self, key: str) -> None:
        """Delete a file from S3/MinIO.

        Args:
            key: The S3 object key (path)

        Raises:
            StorageError: If deletion fails
        """

        def _delete() -> None:
            try:
                self._client.delete_object(Bucket=self.bucket, Key=key)
            except ClientError as e:
                raise StorageError(f"Failed to delete file: {e}") from e

        await asyncio.to_thread(_delete)

    async def file_exists(self, key: str) -> bool:
        """Check if a file exists in S3/MinIO.

        Args:
            key: The S3 object key (path)

        Returns:
            True if file exists, False otherwise
        """

        def _exists() -> bool:
            try:
                self._client.head_object(Bucket=self.bucket, Key=key)
                return True
            except ClientError:
                return False

        return await asyncio.to_thread(_exists)

    async def get_file_info(self, key: str) -> dict[str, str | int]:
        """Get metadata about a file.

        Args:
            key: The S3 object key (path)

        Returns:
            Dict with file metadata (size, content_type, last_modified)

        Raises:
            FileNotFoundError: If file doesn't exist
        """

        def _get_info() -> dict[str, str | int]:
            try:
                response = self._client.head_object(Bucket=self.bucket, Key=key)
                return {
                    "size_bytes": response.get("ContentLength", 0),
                    "content_type": response.get("ContentType", "application/octet-stream"),
                    "etag": response.get("ETag", "").strip('"'),
                    "last_modified": response.get("LastModified", "").isoformat()
                    if response.get("LastModified")
                    else "",
                }
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code in ("404", "NoSuchKey"):
                    raise FileNotFoundError(f"File not found: {key}") from e
                raise StorageError(f"Failed to get file info: {e}") from e

        return await asyncio.to_thread(_get_info)

    def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "get_object",
    ) -> str:
        """Generate a presigned URL for file access.

        Args:
            key: The S3 object key (path)
            expires_in: URL expiration time in seconds (default: 1 hour)
            method: S3 operation ('get_object' for download, 'put_object' for upload)

        Returns:
            Presigned URL string
        """
        url: str = self._client.generate_presigned_url(
            ClientMethod=method,
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return url

    async def generate_presigned_download_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate a presigned URL for downloading a file.

        Args:
            key: The S3 object key (path)
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned download URL

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        # Verify file exists first
        if not await self.file_exists(key):
            raise FileNotFoundError(f"File not found: {key}")

        return self.generate_presigned_url(key, expires_in, "get_object")

    async def generate_presigned_upload_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate a presigned URL for uploading a file.

        Args:
            key: The S3 object key (path)
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned upload URL
        """
        return self.generate_presigned_url(key, expires_in, "put_object")

    async def ensure_bucket_exists(self) -> None:
        """Ensure the configured bucket exists, creating it if necessary."""

        def _ensure_bucket() -> None:
            try:
                self._client.head_bucket(Bucket=self.bucket)
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code in ("404", "NoSuchBucket"):
                    self._client.create_bucket(Bucket=self.bucket)
                else:
                    raise StorageError(f"Failed to check bucket: {e}") from e

        await asyncio.to_thread(_ensure_bucket)


# Singleton instance for dependency injection
_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    """Get or create storage service singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
