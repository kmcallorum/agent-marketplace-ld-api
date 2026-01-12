"""Unit tests for storage module."""

import io
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from agent_marketplace_api.storage import (
    FileNotFoundError,
    StorageError,
    StorageService,
    UploadError,
    UploadResult,
    get_storage_service,
)


@pytest.fixture
def mock_s3_client() -> MagicMock:
    """Create a mock S3 client."""
    return MagicMock()


@pytest.fixture
def storage_service(mock_s3_client: MagicMock) -> StorageService:
    """Create a storage service with mocked S3 client."""
    with patch("agent_marketplace_api.storage.boto3.client", return_value=mock_s3_client):
        service = StorageService(
            endpoint_url="http://localhost:9000",
            access_key="testkey",
            secret_key="testsecret",
            bucket="test-bucket",
            region="us-east-1",
        )
        service._client = mock_s3_client
        return service


class TestStorageServiceInit:
    """Tests for StorageService initialization."""

    def test_init_with_custom_values(self) -> None:
        """Test initialization with custom values."""
        with patch("agent_marketplace_api.storage.boto3.client") as mock_client:
            service = StorageService(
                endpoint_url="http://custom:9000",
                access_key="custom_key",
                secret_key="custom_secret",
                bucket="custom-bucket",
                region="eu-west-1",
            )

            assert service.endpoint_url == "http://custom:9000"
            assert service.access_key == "custom_key"
            assert service.secret_key == "custom_secret"
            assert service.bucket == "custom-bucket"
            assert service.region == "eu-west-1"
            mock_client.assert_called_once()

    def test_init_with_defaults(self) -> None:
        """Test initialization uses default settings."""
        with patch("agent_marketplace_api.storage.boto3.client") as mock_client:
            service = StorageService()

            # Should use settings defaults
            assert service.endpoint_url is not None
            assert service.bucket is not None
            mock_client.assert_called_once()


class TestUploadFile:
    """Tests for upload_file method."""

    @pytest.mark.asyncio
    async def test_upload_bytes_success(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test successful file upload with bytes."""
        mock_s3_client.put_object.return_value = {"ETag": '"abc123"'}

        result = await storage_service.upload_file(
            key="test/file.zip",
            file_data=b"test content",
            content_type="application/zip",
        )

        assert isinstance(result, UploadResult)
        assert result.key == "test/file.zip"
        assert result.bucket == "test-bucket"
        assert result.size_bytes == len(b"test content")
        assert result.etag == "abc123"

        mock_s3_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test/file.zip",
            Body=b"test content",
            ContentType="application/zip",
        )

    @pytest.mark.asyncio
    async def test_upload_file_like_success(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test successful file upload with file-like object."""
        mock_s3_client.put_object.return_value = {"ETag": '"def456"'}
        file_obj = io.BytesIO(b"file content here")

        result = await storage_service.upload_file(
            key="test/file2.zip",
            file_data=file_obj,
        )

        assert result.size_bytes == len(b"file content here")
        assert result.etag == "def456"

    @pytest.mark.asyncio
    async def test_upload_file_failure(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test upload failure raises UploadError."""
        mock_s3_client.put_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Internal error"}},
            "PutObject",
        )

        with pytest.raises(UploadError, match="Failed to upload file"):
            await storage_service.upload_file(
                key="test/fail.zip",
                file_data=b"content",
            )


class TestDownloadFile:
    """Tests for download_file method."""

    @pytest.mark.asyncio
    async def test_download_success(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test successful file download."""
        mock_body = MagicMock()
        mock_body.read.return_value = b"downloaded content"
        mock_s3_client.get_object.return_value = {"Body": mock_body}

        result = await storage_service.download_file("test/file.zip")

        assert result == b"downloaded content"
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test/file.zip",
        )

    @pytest.mark.asyncio
    async def test_download_not_found(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test download of non-existent file raises FileNotFoundError."""
        mock_s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not found"}},
            "GetObject",
        )

        with pytest.raises(FileNotFoundError, match="File not found"):
            await storage_service.download_file("nonexistent.zip")

    @pytest.mark.asyncio
    async def test_download_no_such_key(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test download with NoSuchKey error."""
        mock_s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Key not found"}},
            "GetObject",
        )

        with pytest.raises(FileNotFoundError, match="File not found"):
            await storage_service.download_file("missing.zip")

    @pytest.mark.asyncio
    async def test_download_other_error(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test download with other error raises StorageError."""
        mock_s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "GetObject",
        )

        with pytest.raises(StorageError, match="Failed to download file"):
            await storage_service.download_file("denied.zip")


class TestDeleteFile:
    """Tests for delete_file method."""

    @pytest.mark.asyncio
    async def test_delete_success(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test successful file deletion."""
        mock_s3_client.delete_object.return_value = {}

        await storage_service.delete_file("test/file.zip")

        mock_s3_client.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test/file.zip",
        )

    @pytest.mark.asyncio
    async def test_delete_failure(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test delete failure raises StorageError."""
        mock_s3_client.delete_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Error"}},
            "DeleteObject",
        )

        with pytest.raises(StorageError, match="Failed to delete file"):
            await storage_service.delete_file("test/file.zip")


class TestFileExists:
    """Tests for file_exists method."""

    @pytest.mark.asyncio
    async def test_file_exists_true(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test file_exists returns True when file exists."""
        mock_s3_client.head_object.return_value = {}

        result = await storage_service.file_exists("test/file.zip")

        assert result is True

    @pytest.mark.asyncio
    async def test_file_exists_false(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test file_exists returns False when file doesn't exist."""
        mock_s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not found"}},
            "HeadObject",
        )

        result = await storage_service.file_exists("nonexistent.zip")

        assert result is False


class TestGetFileInfo:
    """Tests for get_file_info method."""

    @pytest.mark.asyncio
    async def test_get_file_info_success(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test successful get_file_info."""
        from datetime import datetime

        mock_s3_client.head_object.return_value = {
            "ContentLength": 1024,
            "ContentType": "application/zip",
            "ETag": '"etag123"',
            "LastModified": datetime(2025, 1, 1, 12, 0, 0),
        }

        result = await storage_service.get_file_info("test/file.zip")

        assert result["size_bytes"] == 1024
        assert result["content_type"] == "application/zip"
        assert result["etag"] == "etag123"
        assert "2025-01-01" in str(result["last_modified"])

    @pytest.mark.asyncio
    async def test_get_file_info_not_found(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test get_file_info raises FileNotFoundError."""
        mock_s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not found"}},
            "HeadObject",
        )

        with pytest.raises(FileNotFoundError, match="File not found"):
            await storage_service.get_file_info("nonexistent.zip")

    @pytest.mark.asyncio
    async def test_get_file_info_other_error(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test get_file_info with other error raises StorageError."""
        mock_s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "HeadObject",
        )

        with pytest.raises(StorageError, match="Failed to get file info"):
            await storage_service.get_file_info("denied.zip")

    @pytest.mark.asyncio
    async def test_get_file_info_no_last_modified(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test get_file_info when LastModified is missing."""
        mock_s3_client.head_object.return_value = {
            "ContentLength": 512,
            "ContentType": "text/plain",
            "ETag": '"etag456"',
        }

        result = await storage_service.get_file_info("test/file.txt")

        assert result["size_bytes"] == 512
        assert result["last_modified"] == ""


class TestPresignedUrls:
    """Tests for presigned URL generation."""

    def test_generate_presigned_url(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test presigned URL generation."""
        mock_s3_client.generate_presigned_url.return_value = "https://presigned.url"

        result = storage_service.generate_presigned_url(
            key="test/file.zip",
            expires_in=7200,
            method="get_object",
        )

        assert result == "https://presigned.url"
        mock_s3_client.generate_presigned_url.assert_called_once_with(
            ClientMethod="get_object",
            Params={"Bucket": "test-bucket", "Key": "test/file.zip"},
            ExpiresIn=7200,
        )

    @pytest.mark.asyncio
    async def test_generate_presigned_download_url(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test presigned download URL generation."""
        mock_s3_client.head_object.return_value = {}  # File exists
        mock_s3_client.generate_presigned_url.return_value = "https://download.url"

        result = await storage_service.generate_presigned_download_url("test/file.zip")

        assert result == "https://download.url"

    @pytest.mark.asyncio
    async def test_generate_presigned_download_url_not_found(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test presigned download URL raises error for non-existent file."""
        mock_s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not found"}},
            "HeadObject",
        )

        with pytest.raises(FileNotFoundError, match="File not found"):
            await storage_service.generate_presigned_download_url("nonexistent.zip")

    @pytest.mark.asyncio
    async def test_generate_presigned_upload_url(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test presigned upload URL generation."""
        mock_s3_client.generate_presigned_url.return_value = "https://upload.url"

        result = await storage_service.generate_presigned_upload_url("test/new.zip")

        assert result == "https://upload.url"


class TestEnsureBucketExists:
    """Tests for ensure_bucket_exists method."""

    @pytest.mark.asyncio
    async def test_bucket_already_exists(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test when bucket already exists."""
        mock_s3_client.head_bucket.return_value = {}

        await storage_service.ensure_bucket_exists()

        mock_s3_client.head_bucket.assert_called_once_with(Bucket="test-bucket")
        mock_s3_client.create_bucket.assert_not_called()

    @pytest.mark.asyncio
    async def test_bucket_creates_if_not_exists(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test bucket creation when it doesn't exist."""
        mock_s3_client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not found"}},
            "HeadBucket",
        )
        mock_s3_client.create_bucket.return_value = {}

        await storage_service.ensure_bucket_exists()

        mock_s3_client.create_bucket.assert_called_once_with(Bucket="test-bucket")

    @pytest.mark.asyncio
    async def test_bucket_creates_if_no_such_bucket(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test bucket creation with NoSuchBucket error."""
        mock_s3_client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}},
            "HeadBucket",
        )
        mock_s3_client.create_bucket.return_value = {}

        await storage_service.ensure_bucket_exists()

        mock_s3_client.create_bucket.assert_called_once()

    @pytest.mark.asyncio
    async def test_bucket_other_error(
        self,
        storage_service: StorageService,
        mock_s3_client: MagicMock,
    ) -> None:
        """Test bucket check with other error raises StorageError."""
        mock_s3_client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "HeadBucket",
        )

        with pytest.raises(StorageError, match="Failed to check bucket"):
            await storage_service.ensure_bucket_exists()


class TestGetStorageService:
    """Tests for get_storage_service singleton."""

    def test_returns_singleton(self) -> None:
        """Test that get_storage_service returns same instance."""
        # Reset the singleton
        import agent_marketplace_api.storage as storage_module

        storage_module._storage_service = None

        with patch("agent_marketplace_api.storage.boto3.client"):
            service1 = get_storage_service()
            service2 = get_storage_service()

            assert service1 is service2

        # Clean up
        storage_module._storage_service = None


class TestUploadResult:
    """Tests for UploadResult dataclass."""

    def test_upload_result_creation(self) -> None:
        """Test UploadResult creation."""
        result = UploadResult(
            key="test/file.zip",
            bucket="my-bucket",
            size_bytes=1024,
            etag="abc123",
        )

        assert result.key == "test/file.zip"
        assert result.bucket == "my-bucket"
        assert result.size_bytes == 1024
        assert result.etag == "abc123"
