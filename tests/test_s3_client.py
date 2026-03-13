from unittest.mock import MagicMock, patch

from src.integrations.s3.client import S3Client


def test_build_key_format():
    client = S3Client(bucket="test-bucket")
    key = client._build_key("manual.pdf", category="marca")
    assert key.startswith("knowledge/marca/manual-")
    assert key.endswith(".pdf")


def test_build_key_unique():
    client = S3Client(bucket="test-bucket")
    key1 = client._build_key("test.pdf", category="geral")
    key2 = client._build_key("test.pdf", category="geral")
    assert key1 != key2


def test_build_key_long_name_truncated():
    client = S3Client(bucket="test-bucket")
    long_name = "a" * 100 + ".docx"
    key = client._build_key(long_name, category="marca")
    assert key.startswith("knowledge/marca/")
    # stem is truncated to 50 chars
    parts = key.split("/")
    filename = parts[-1]
    assert len(filename) < 70  # 50 stem + 8 uuid + 1 dash + ext


@patch("src.integrations.s3.client.boto3")
def test_upload_calls_put_object(mock_boto3):
    mock_s3 = MagicMock()
    mock_boto3.client.return_value = mock_s3

    client = S3Client(bucket="my-bucket")
    key = client.upload(b"file content", "test.pdf", "application/pdf", "marca")

    mock_s3.put_object.assert_called_once()
    call_kwargs = mock_s3.put_object.call_args[1]
    assert call_kwargs["Bucket"] == "my-bucket"
    assert call_kwargs["Body"] == b"file content"
    assert call_kwargs["ContentType"] == "application/pdf"
    assert key.startswith("knowledge/marca/")


@patch("src.integrations.s3.client.boto3")
def test_delete_calls_delete_object(mock_boto3):
    mock_s3 = MagicMock()
    mock_boto3.client.return_value = mock_s3

    client = S3Client(bucket="my-bucket")
    client.delete("knowledge/marca/test-abc123.pdf")

    mock_s3.delete_object.assert_called_once_with(
        Bucket="my-bucket", Key="knowledge/marca/test-abc123.pdf"
    )


@patch("src.integrations.s3.client.boto3")
def test_presigned_url(mock_boto3):
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://s3.example.com/test"
    mock_boto3.client.return_value = mock_s3

    client = S3Client(bucket="my-bucket")
    url = client.presigned_url("knowledge/test.pdf", expires_in=600)

    assert url == "https://s3.example.com/test"
    mock_s3.generate_presigned_url.assert_called_once()
